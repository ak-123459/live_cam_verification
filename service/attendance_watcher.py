"""
attendance_watcher.py
─────────────────────
Monitors  ./unknown_faces/<YYYYMMDD>/  every INTERVAL seconds.
Sends every pending image to  POST /attendance/batch  in one multipart call.
Deletes files whose attendance was successfully registered.

Filename convention expected:
    20260312_171840_475679.jpg
    └──date─┘ └time┘

Optimisations
─────────────
• aiofiles  → non-blocking reads  (zero blocking I/O in event-loop)
• aiohttp   → single persistent TCP session; multipart streaming
• in_flight → never sends the same file twice concurrently
• asyncio.gather → all file reads fire in parallel
• no caching → bytes are read → sent → freed immediately
• MAX_BATCH → caps memory per cycle
"""

from __future__ import annotations
from urllib.parse import unquote   # add at top of file
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp

# ── config  (override via env vars) ──────────────────────────────────────────
WATCH_DIR   = Path(os.getenv("WATCH_DIR",  "./captures/unknown"))
API_URL     = os.getenv("API_URL",         "http://[::1]:8004/attendance/batch")
CAMERA_ID   = os.getenv("CAMERA_ID",       "CAM_01")
INTERVAL    = float(os.getenv("INTERVAL",  "5"))   # seconds between cycles
MAX_BATCH   = int(os.getenv("MAX_BATCH",   "30"))  # max images per HTTP call
EXTENSIONS  = {".jpg", ".jpeg", ".png"}




# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("watcher")

# ── filename → (date_str, time_str) ──────────────────────────────────────────
_FN_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})")

def parse_filename_datetime(stem: str) -> tuple[str, str]:
    """
    '20260312_171840_475679'  →  ('2026-03-12', '17:18:40')
    Falls back to current datetime if pattern does not match.
    """
    m = _FN_RE.match(stem)
    if m:
        yr, mo, dy, hh, mm, ss = m.groups()
        return f"{yr}-{mo}-{dy}", f"{hh}:{mm}:{ss}"
    now = datetime.now()
    return now.date().isoformat(), now.strftime("%H:%M:%S")


# ── collect pending files ─────────────────────────────────────────────────────
def collect_pending(in_flight: set[Path]) -> list[Path]:
    pending: list[Path] = []
    found_dates: list[str] = []
    try:
        with os.scandir(WATCH_DIR) as top:
            for date_entry in top:
                if not date_entry.is_dir():
                    continue
                found_dates.append(date_entry.name)
                with os.scandir(date_entry.path) as day:
                    for f in day:
                        if not f.is_file():
                            continue
                        p = Path(f.path)
                        if p.suffix.lower() not in EXTENSIONS:
                            continue
                        if p in in_flight:
                            continue
                        pending.append(p)
                        if len(pending) >= MAX_BATCH:
                            return pending
    except FileNotFoundError:
        pass
    if found_dates:
        log.debug("scan: date_dirs=%s  pending=%d", sorted(found_dates), len(pending))
    return pending



# ── read one file  (non-blocking) ─────────────────────────────────────────────
async def _read(path: Path) -> Optional[bytes]:
    try:
        async with aiofiles.open(path, "rb") as fh:
            return await fh.read()
    except OSError as exc:
        log.warning("read error %s: %s", path.name, exc)
        return None


# ── one attendance cycle ──────────────────────────────────────────────────────
async def run_cycle(
    session:   aiohttp.ClientSession,
    in_flight: set[Path],
) -> None:
    pending = collect_pending(in_flight)
    if not pending:
        return

    # Lock before any await → concurrent cycles won't re-pick same files
    in_flight.update(pending)
    log.info("cycle: %d file(s) to process", len(pending))

    # ── parallel non-blocking file reads ─────────────────────────────────────
    contents: list[Optional[bytes]] = await asyncio.gather(
        *(_read(p) for p in pending)
    )

    form = aiohttp.FormData()
    sent_map: dict[str, Path] = {}  # tagged_name  → Path  (for tagged lookup)
    bare_map: dict[str, Path] = {}  # bare filename → Path  (for server response lookup)

    # track which date folders are in this batch
    dates_in_batch: set[str] = set()

    for path, data in zip(pending, contents):
        if data is None:
            in_flight.discard(path)
            continue

        date_str, time_str = parse_filename_datetime(path.stem)
        dates_in_batch.add(date_str)

        tagged_name = f"{path.name}|{date_str}|{time_str}"

        form.add_field(
            "files",
            data,
            filename=tagged_name,
            content_type="image/jpeg",
        )
        sent_map[tagged_name] = path
        bare_map[path.name] = path  # ← bare name map

    if not sent_map:
        in_flight.difference_update(pending)
        return

    form.add_field("camera_id", CAMERA_ID)

    log.info("cycle: processing dates=%s  files=%d",
             sorted(dates_in_batch), len(sent_map))  # ← date logging



    # ── POST to attendance API ────────────────────────────────────────────────
    try:
        async with session.post(API_URL, data=form) as resp:
            if resp.status != 200:
                body = await resp.text()
                log.error("API %d: %s", resp.status, body[:300])
                in_flight.difference_update(pending)
                return
            result: dict = await resp.json()
    except aiohttp.ClientError as exc:
        log.error("HTTP error: %s", exc)
        in_flight.difference_update(pending)
        return

    # ── delete files after server confirms processing ─────────────────────────
    for frame in result.get("frames", []):
        raw_fname = frame.get("filename", "")
        fname = unquote(raw_fname)  # decode %7C→| and %3A→:

        # try tagged name first, then bare filename
        local_path = sent_map.get(fname) or bare_map.get(fname.split("|")[0])

        if local_path is None:
            log.warning("no local file found for filename=%r", raw_fname)
            continue

        try:
            local_path.unlink(missing_ok=True)

            # prune empty date directory
            try:
                local_path.parent.rmdir()
            except OSError:
                pass

            if frame.get("attendance_new") or frame.get("f"):
                log.info(
                    "✓ registered  user_id=%-4s  sim=%.4f  %s",
                    frame.get("user_id", "?"),
                    frame.get("similarity", 0.0),
                    local_path.name,
                )
            elif frame.get("error"):
                log.warning(
                    "✗ error=%s  deleted  %s",
                    frame.get("error"), local_path.name,
                )
            else:
                log.debug("already marked — deleted %s", local_path.name)

        except OSError as exc:
            log.warning("delete error %s: %s", local_path.name, exc)

    log.info(
        "cycle done — total=%d matched=%d new=%d errors=%d  %.0fms",
        result.get("total", 0),
        result.get("matched", 0),
        result.get("attendance_new", 0),
        result.get("errors", 0),
        result.get("elapsed_ms", 0),
    )

    in_flight.difference_update(pending)


# ── main loop ─────────────────────────────────────────────────────────────────
async def main() -> None:
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    log.info(
        "Watcher started — dir=%s  interval=%.1fs  batch=%d  api=%s",
        WATCH_DIR, INTERVAL, MAX_BATCH, API_URL,
    )

    in_flight: set[Path] = set()

    connector = aiohttp.TCPConnector(limit=4, ttl_dns_cache=300)
    timeout   = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        while True:
            t0 = asyncio.get_event_loop().time()
            try:
                await run_cycle(session, in_flight)
            except Exception as exc:
                log.exception("unexpected cycle error: %s", exc)

            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(0.0, INTERVAL - elapsed))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Watcher stopped.")