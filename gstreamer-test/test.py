"""
stream_viewer.py
────────────────
GStreamer-powered live stream viewer with real-time stats overlay.

Supports:
  • RTSP cameras     →  rtsp://user:pass@192.168.1.100:554/stream
  • USB / V4L2 cams  →  /dev/video0  or  0  (index)
  • Video files      →  /path/to/file.mp4
  • Test pattern     →  test  (no camera needed)

Usage:
  python stream_viewer.py                          # test pattern
  python stream_viewer.py rtsp://192.168.1.10/live # RTSP
  python stream_viewer.py /dev/video0              # USB cam
  python stream_viewer.py /path/video.mp4          # file
  python stream_viewer.py 0                        # cam index

Controls (OpenCV window):
  q / ESC  → quit
  s        → save current frame as PNG
  f        → toggle stats overlay
  r        → reset stats counters

Requirements:
  pip install opencv-python numpy
  # GStreamer + Python bindings:
  # Ubuntu/Debian: sudo apt install python3-gst-1.0 gstreamer1.0-tools
  #                gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
  #                gstreamer1.0-plugins-ugly gstreamer1.0-libav
  # Windows:       Install GStreamer from https://gstreamer.freedesktop.org/download/
  #                Then: pip install PyGObject
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import threading
import queue
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ── GStreamer import ──────────────────────────────────────────────────────────
try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp, GLib
    Gst.init(None)
    GST_AVAILABLE = True
except Exception as e:
    print(f"[WARN] GStreamer bindings not available: {e}")
    print("[WARN] Falling back to OpenCV backend.")
    GST_AVAILABLE = False

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("stream_viewer")

# ── constants ─────────────────────────────────────────────────────────────────
FRAME_QUEUE_SIZE  = 10          # max buffered frames
STATS_WINDOW      = 60          # rolling window for FPS calc (frames)
SAVE_DIR          = Path("./saved_frames")
FONT              = cv2.FONT_HERSHEY_SIMPLEX

# ── colour palette (BGR) ──────────────────────────────────────────────────────
C_GREEN  = (80,  210, 80)
C_RED    = (60,  60,  230)
C_AMBER  = (30,  165, 230)
C_WHITE  = (240, 240, 240)
C_BLACK  = (20,  20,  20)
C_TEAL   = (180, 200, 60)
C_PANEL  = (30,  30,  30)       # stats panel background


# ══════════════════════════════════════════════════════════════════════════════
#  Stats tracker
# ══════════════════════════════════════════════════════════════════════════════
class StreamStats:
    """Thread-safe rolling stats for the live overlay."""

    def __init__(self, window: int = STATS_WINDOW) -> None:
        self._lock          = threading.Lock()
        self._window        = window
        self._timestamps: deque[float] = deque(maxlen=window)
        self._frame_sizes: deque[int]  = deque(maxlen=window)
        self.total_frames   = 0
        self.dropped_frames = 0
        self.decode_times: deque[float] = deque(maxlen=window)
        self.start_time     = time.monotonic()
        self.last_frame_ts  = 0.0
        self.width          = 0
        self.height         = 0
        self.source         = ""
        self.backend        = ""
        self.connected      = False

    def record_frame(self, frame: np.ndarray, decode_ms: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._timestamps.append(now)
            self._frame_sizes.append(frame.nbytes)
            self.decode_times.append(decode_ms)
            self.total_frames += 1
            self.last_frame_ts = now
            self.height, self.width = frame.shape[:2]
            self.connected = True

    def record_drop(self) -> None:
        with self._lock:
            self.dropped_frames += 1

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()
            self._frame_sizes.clear()
            self.decode_times.clear()
            self.total_frames   = 0
            self.dropped_frames = 0
            self.start_time     = time.monotonic()

    # ── computed properties ───────────────────────────────────────────────────
    @property
    def fps(self) -> float:
        with self._lock:
            ts = list(self._timestamps)
        if len(ts) < 2:
            return 0.0
        span = ts[-1] - ts[0]
        return (len(ts) - 1) / span if span > 0 else 0.0

    @property
    def avg_decode_ms(self) -> float:
        with self._lock:
            d = list(self.decode_times)
        return sum(d) / len(d) if d else 0.0

    @property
    def throughput_mbps(self) -> float:
        """Approximate pixel throughput in MB/s."""
        with self._lock:
            sizes = list(self._frame_sizes)
            ts    = list(self._timestamps)
        if len(ts) < 2:
            return 0.0
        span = ts[-1] - ts[0]
        return (sum(sizes) / 1_048_576) / span if span > 0 else 0.0

    @property
    def uptime_str(self) -> str:
        secs  = int(time.monotonic() - self.start_time)
        h, r  = divmod(secs, 3600)
        m, s  = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def staleness_ms(self) -> float:
        if not self.last_frame_ts:
            return 0.0
        return (time.monotonic() - self.last_frame_ts) * 1000


# ══════════════════════════════════════════════════════════════════════════════
#  GStreamer pipeline builder
# ══════════════════════════════════════════════════════════════════════════════
def build_pipeline_string(source: str) -> str:
    """
    Returns a GStreamer pipeline string that ends with appsink.
    Detects source type from the source argument.
    """
    caps = "video/x-raw,format=BGR"   # OpenCV-friendly

    # test pattern
    if source.lower() == "test":
        return (
            f"videotestsrc pattern=ball ! "
            f"videoconvert ! {caps} ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
        )

    # RTSP
    if source.lower().startswith("rtsp://"):
        return (
            f"rtspsrc location={source} latency=200 ! "
            f"rtph264depay ! h264parse ! avdec_h264 ! "
            f"videoconvert ! {caps} ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
        )

    # USB / V4L2 (Linux) — numeric index or /dev/videoX
    if source.isdigit() or source.startswith("/dev/video"):
        idx = source if source.startswith("/dev/") else f"/dev/video{source}"
        return (
            f"v4l2src device={idx} ! "
            f"videoconvert ! {caps} ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
        )

    # Windows DirectShow camera (numeric index on Windows)
    if source.isdigit() and sys.platform == "win32":
        return (
            f"ksvideosrc device-index={source} ! "
            f"videoconvert ! {caps} ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
        )

    # Video file
    return (
        f"filesrc location={source} ! "
        f"decodebin ! "
        f"videoconvert ! {caps} ! "
        f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  GStreamer reader thread
# ══════════════════════════════════════════════════════════════════════════════
class GStreamerReader(threading.Thread):
    """
    Runs a GStreamer pipeline in a background thread.
    Pushes decoded frames into `frame_queue`.
    """

    def __init__(
        self,
        source:      str,
        frame_queue: queue.Queue,
        stats:       StreamStats,
    ) -> None:
        super().__init__(daemon=True, name="gst-reader")
        self.source      = source
        self.frame_queue = frame_queue
        self.stats       = stats
        self._stop_evt   = threading.Event()
        self.pipeline    = None
        self.error: Optional[str] = None

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        pipe_str = build_pipeline_string(self.source)
        log.info("GStreamer pipeline:\n  %s", pipe_str)

        try:
            pipeline = Gst.parse_launch(pipe_str)
        except Exception as exc:
            self.error = str(exc)
            log.error("Pipeline parse error: %s", exc)
            return

        self.pipeline = pipeline
        appsink = pipeline.get_by_name("sink")
        appsink.set_property("emit-signals", True)
        appsink.set_property("max-buffers", 2)
        appsink.set_property("drop", True)

        pipeline.set_state(Gst.State.PLAYING)
        log.info("Pipeline PLAYING — source: %s", self.source)

        bus = pipeline.get_bus()

        while not self._stop_evt.is_set():
            # ── pull sample ───────────────────────────────────────────────────
            t0     = time.monotonic()
            sample = appsink.try_pull_sample(Gst.SECOND // 10)   # 100ms timeout
            if sample is None:
                # check bus for errors
                msg = bus.timed_pop_filtered(
                    0,
                    Gst.MessageType.ERROR | Gst.MessageType.EOS,
                )
                if msg:
                    if msg.type == Gst.MessageType.ERROR:
                        err, dbg = msg.parse_error()
                        self.error = str(err)
                        log.error("GStreamer error: %s — %s", err, dbg)
                    elif msg.type == Gst.MessageType.EOS:
                        log.info("End of stream.")
                    break
                continue

            # ── buffer → numpy ────────────────────────────────────────────────
            buf    = sample.get_buffer()
            caps   = sample.get_caps()
            struct = caps.get_structure(0)
            w      = struct.get_value("width")
            h      = struct.get_value("height")

            ok, map_info = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue

            try:
                frame = np.frombuffer(map_info.data, dtype=np.uint8)
                frame = frame.reshape((h, w, 3)).copy()
            finally:
                buf.unmap(map_info)

            decode_ms = (time.monotonic() - t0) * 1000

            # ── push to queue (drop if full) ──────────────────────────────────
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                    self.stats.record_drop()
                except queue.Empty:
                    pass

            self.frame_queue.put(frame)
            self.stats.record_frame(frame, decode_ms)

        pipeline.set_state(Gst.State.NULL)
        log.info("Pipeline stopped.")


# ══════════════════════════════════════════════════════════════════════════════
#  OpenCV fallback reader (no GStreamer)
# ══════════════════════════════════════════════════════════════════════════════
class OpenCVReader(threading.Thread):
    """
    Fallback reader using OpenCV VideoCapture.
    Same interface as GStreamerReader.
    """

    def __init__(
        self,
        source:      str,
        frame_queue: queue.Queue,
        stats:       StreamStats,
    ) -> None:
        super().__init__(daemon=True, name="cv-reader")
        self.source      = source if not source.isdigit() else int(source)
        self.frame_queue = frame_queue
        self.stats       = stats
        self._stop_evt   = threading.Event()
        self.error: Optional[str] = None

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.error = f"Cannot open source: {self.source}"
            log.error(self.error)
            return

        log.info("OpenCV reader started — source: %s", self.source)

        while not self._stop_evt.is_set():
            t0 = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                log.info("Stream ended / no frame.")
                break

            decode_ms = (time.monotonic() - t0) * 1000

            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                    self.stats.record_drop()
                except queue.Empty:
                    pass

            self.frame_queue.put(frame)
            self.stats.record_frame(frame, decode_ms)

            time.sleep(0.01)   # ~100fps cap to avoid tight spin

        cap.release()
        log.info("OpenCV reader stopped.")


# ══════════════════════════════════════════════════════════════════════════════
#  Stats overlay renderer
# ══════════════════════════════════════════════════════════════════════════════
def draw_stats(frame: np.ndarray, stats: StreamStats) -> np.ndarray:
    """
    Draws a semi-transparent stats panel on the frame.
    Returns the annotated frame (does NOT modify in place).
    """
    out    = frame.copy()
    h, w   = out.shape[:2]

    # ── panel geometry ────────────────────────────────────────────────────────
    panel_w = 310
    panel_h = 260
    margin  = 12
    px      = w - panel_w - margin
    py      = margin

    # semi-transparent dark background
    overlay = out.copy()
    cv2.rectangle(overlay, (px - 8, py - 8),
                  (px + panel_w, py + panel_h), C_PANEL, -1)
    cv2.addWeighted(overlay, 0.72, out, 0.28, 0, out)

    # ── header ────────────────────────────────────────────────────────────────
    cv2.putText(out, "LIVE STREAM STATS",
                (px, py + 14), FONT, 0.42, C_TEAL, 1, cv2.LINE_AA)

    # divider
    cv2.line(out, (px - 8, py + 20), (px + panel_w, py + 20), C_TEAL, 1)

    # ── stat rows ─────────────────────────────────────────────────────────────
    fps         = stats.fps
    fps_color   = C_GREEN if fps >= 20 else (C_AMBER if fps >= 10 else C_RED)

    decode_ms   = stats.avg_decode_ms
    dec_color   = C_GREEN if decode_ms < 20 else (C_AMBER if decode_ms < 50 else C_RED)

    dropped     = stats.dropped_frames
    drop_color  = C_GREEN if dropped == 0 else (C_AMBER if dropped < 10 else C_RED)

    stale_ms    = stats.staleness_ms
    stale_color = C_GREEN if stale_ms < 200 else (C_AMBER if stale_ms < 500 else C_RED)

    rows = [
        ("Source",    stats.source[:28],                              C_WHITE),
        ("Backend",   stats.backend,                                  C_WHITE),
        ("Resolution",f"{stats.width} x {stats.height}",             C_WHITE),
        ("FPS",       f"{fps:6.1f}",                                  fps_color),
        ("Decode",    f"{decode_ms:6.1f} ms",                         dec_color),
        ("Throughput",f"{stats.throughput_mbps:5.1f} MB/s",          C_WHITE),
        ("Frames",    f"{stats.total_frames:,}",                      C_WHITE),
        ("Dropped",   f"{dropped:,}",                                 drop_color),
        ("Staleness", f"{stale_ms:6.0f} ms",                         stale_color),
        ("Uptime",    stats.uptime_str,                               C_WHITE),
    ]

    y = py + 36
    for label, value, color in rows:
        cv2.putText(out, f"{label:<12}", (px, y),
                    FONT, 0.36, C_WHITE, 1, cv2.LINE_AA)
        cv2.putText(out, value, (px + 110, y),
                    FONT, 0.36, color, 1, cv2.LINE_AA)
        y += 20

    # ── timestamp watermark (bottom-left) ─────────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(out, ts, (10, h - 10),
                FONT, 0.38, C_WHITE, 1, cv2.LINE_AA)

    # ── FPS bar (bottom strip) ────────────────────────────────────────────────
    bar_w  = int(min(fps / 30.0, 1.0) * 200)
    bar_y  = h - 6
    cv2.rectangle(out, (10, bar_y - 4), (210, bar_y), (50, 50, 50), -1)
    cv2.rectangle(out, (10, bar_y - 4), (10 + bar_w, bar_y), fps_color, -1)
    cv2.putText(out, "FPS", (215, bar_y),
                FONT, 0.3, C_WHITE, 1, cv2.LINE_AA)

    return out


# ══════════════════════════════════════════════════════════════════════════════
#  Main viewer
# ══════════════════════════════════════════════════════════════════════════════
def run_viewer(source: str) -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    stats              = StreamStats()
    stats.source       = source
    frame_queue: queue.Queue = queue.Queue(maxsize=FRAME_QUEUE_SIZE)

    # ── choose backend ────────────────────────────────────────────────────────
    if GST_AVAILABLE:
        reader = GStreamerReader(source, frame_queue, stats)
        stats.backend = "GStreamer"
    else:
        reader = OpenCVReader(source, frame_queue, stats)
        stats.backend = "OpenCV (fallback)"

    reader.start()
    log.info("Backend: %s", stats.backend)

    show_stats   = True
    window_name  = f"Stream Viewer — {source}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    log.info("Controls:  q/ESC=quit  s=save frame  f=toggle stats  r=reset counters")

    # ── main display loop ─────────────────────────────────────────────────────
    while True:
        # ── get frame ─────────────────────────────────────────────────────────
        try:
            frame = frame_queue.get(timeout=2.0)
        except queue.Empty:
            if not reader.is_alive():
                log.warning("Reader thread died — %s", reader.error or "unknown reason")
                break
            # show "waiting" placeholder
            placeholder = np.zeros((480, 854, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Waiting for stream...",
                        (220, 240), FONT, 0.9, C_AMBER, 2, cv2.LINE_AA)
            cv2.imshow(window_name, placeholder)
            key = cv2.waitKey(100) & 0xFF
            if key in (ord("q"), 27):
                break
            continue

        # ── draw overlay ──────────────────────────────────────────────────────
        display = draw_stats(frame, stats) if show_stats else frame.copy()

        cv2.imshow(window_name, display)

        # ── keyboard ──────────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), 27):          # q / ESC → quit
            break

        elif key == ord("s"):              # s → save frame
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = SAVE_DIR / f"frame_{ts}.png"
            cv2.imwrite(str(path), frame)
            log.info("Saved frame → %s", path)

        elif key == ord("f"):              # f → toggle stats
            show_stats = not show_stats
            log.info("Stats overlay: %s", "ON" if show_stats else "OFF")

        elif key == ord("r"):              # r → reset counters
            stats.reset()
            log.info("Stats reset.")

    # ── cleanup ───────────────────────────────────────────────────────────────
    reader.stop()
    cv2.destroyAllWindows()
    log.info("Viewer closed.")


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description="GStreamer live stream viewer with real-time stats overlay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stream_viewer.py                              # test pattern
  python stream_viewer.py rtsp://admin:1234@192.168.1.10:554/stream1
  python stream_viewer.py /dev/video0
  python stream_viewer.py 0
  python stream_viewer.py /path/to/video.mp4
        """,
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="test",
        help="Stream source: RTSP URL | device path | camera index | file path | 'test'",
    )
    args = parser.parse_args()
    run_viewer(args.source)


if __name__ == "__main__":
    main()