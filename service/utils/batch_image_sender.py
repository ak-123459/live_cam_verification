"""
Batch Image Sender
------------------
Reads all face.jpg images from captures/unknown/ directory
and sends them in batches to the API
"""

import os
import requests
from pathlib import Path
import time


# AFTER ✅ — goes up 2 levels to PAI_AATS/captures/unknown
_SCRIPT_DIR  = Path(__file__).resolve().parent    # PAI_AATS/service/utils/
_PROJECT_DIR = _SCRIPT_DIR.parent.parent           # PAI_AATS/
CAPTURES_DIR = _PROJECT_DIR / "captures" / "unknown"

# ── Config ────────────────────────────────────────────────────
API_URL        = "http://localhost:8003/images/upload"
BATCH_SIZE     = 10    # how many images per API call


def get_all_image_paths(base_dir: str) -> list:
    """
    Scan captures/unknown/ — multiple images per time folder.

    Exact structure:
        captures/unknown/
            {YYYYMMDD}/           ← date folder
                {HHMMSS_ffffff}/  ← time folder
                    face1.jpg     ← collected
                    face2.jpg     ← collected
                    face3.png     ← collected
                    ...

    Collects ALL .jpg / .jpeg / .png files inside each time folder.
    """
    base = Path(base_dir)

    if not base.exists():
        print(f"❌ Directory not found: {base_dir}")
        return []

    # ── Allowed extensions ────────────────────────────────────
    ALLOWED_EXT = {".jpg", ".jpeg", ".png"}

    paths = []

    # ── Walk exact 2-level structure: date → time_id → images ─
    for date_folder in sorted(base.iterdir()):
        if not date_folder.is_dir():
            continue

        for time_folder in sorted(date_folder.iterdir()):
            if not time_folder.is_dir():
                continue

            # Collect ALL valid images in this time folder
            for img_file in sorted(time_folder.iterdir()):
                if (
                    img_file.is_file()
                    and img_file.suffix.lower() in ALLOWED_EXT
                ):
                    paths.append(img_file)

    # ── Summary ───────────────────────────────────────────────
    print(f"✅ Found {len(paths)} images in {base_dir}")
    print(f"   Structure : {base_dir}/YYYYMMDD/HHMMSS_ffffff/face*.jpg")

    # Per-date breakdown
    date_counts = {}
    for p in paths:
        date = p.parts[-3]   # 20260307
        date_counts[date] = date_counts.get(date, 0) + 1

    for date, count in sorted(date_counts.items()):
        print(f"   {date} : {count} images")

    return paths


def send_batch_to_api(img_paths: list, api_url: str) -> dict:
    """
    Send a batch of images to the API

    Args:
        img_paths : list of Path objects
        api_url   : API endpoint URL

    Returns:
        API response dict
    """

    # ── MIME type map ─────────────────────────────────────────
    MIME_MAP = {
        ".jpg"  : "image/jpeg",
        ".jpeg" : "image/jpeg",
        ".png"  : "image/png",
    }

    files = []

    for path in img_paths:
        mime_type = MIME_MAP.get(path.suffix.lower(), "image/jpeg")
        try:
            f = open(path, "rb")
            files.append(
                ("files", (path.name, f, mime_type))
            )
        except Exception as e:
            print(f"  ❌ Could not open {path}: {e}")

    if not files:
        return {}

    try:
        response = requests.post(api_url, files=files, timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        print(f"  ❌ Cannot connect to API at {api_url}")
        return {}

    except requests.exceptions.Timeout:
        print(f"  ❌ Request timed out")
        return {}

    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return {}

    finally:
        # Always close file handles
        for _, (_, f, _) in files:
            f.close()


def process_all_captures(
    base_dir   : str  = CAPTURES_DIR,
    api_url    : str  = API_URL,
    batch_size : int  = BATCH_SIZE,
):
    """
    Main function — reads all images and sends to API in batches

    Args:
        base_dir   : root captures directory
        api_url    : API endpoint
        batch_size : images per API call
    """

    print("=" * 55)
    print("  BATCH IMAGE SENDER")
    print("=" * 55)
    print(f"  Directory  : {base_dir}")
    print(f"  API URL    : {api_url}")
    print(f"  Batch size : {batch_size}")
    print("=" * 55)

    # ── Collect all paths ─────────────────────────────────────
    all_paths     = get_all_image_paths(base_dir)

    if not all_paths:
        print("No images found. Exiting.")
        return

    total         = len(all_paths)
    total_batches = (total + batch_size - 1) // batch_size
    all_results   = []

    print(f"\nSending {total} images in {total_batches} batches...\n")

    # ── Send in batches ───────────────────────────────────────
    for i in range(0, total, batch_size):
        chunk      = all_paths[i : i + batch_size]
        batch_num  = i // batch_size + 1

        print(f"── Batch {batch_num}/{total_batches} ({len(chunk)} images)")
        for p in chunk:
            print(f"   📄 {p}")

        t0       = time.time()
        result   = send_batch_to_api(chunk, api_url)
        elapsed  = (time.time() - t0) * 1000

        if result:
            print(f"   ✅ Response  : {result}")
            print(f"   ⏱  Time     : {elapsed:.1f}ms")
            all_results.extend(result.get("images", []))
        else:
            print(f"   ❌ No response for batch {batch_num}")

        print()

    # ── Summary ───────────────────────────────────────────────
    print("=" * 55)
    print(f"  DONE")
    print(f"  Total sent     : {total}")
    print(f"  Total returned : {len(all_results)}")
    print("=" * 55)

    return all_results


# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    process_all_captures(
        base_dir   = CAPTURES_DIR,
        api_url    = API_URL,
        batch_size = BATCH_SIZE,
    )