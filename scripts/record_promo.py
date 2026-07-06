"""Record PandaBook promo slideshow → MP4 + PNG screenshots.

Requires: server on :8000, playwright chromium.

  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  python scripts/record_promo.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "promo"
URL = "http://127.0.0.1:8000/promo.html"


def wait_server(timeout: float = 30) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(URL, timeout=2) as r:
                return r.status == 200
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium")
        return 1

    if not wait_server():
        print(f"Start server first: uvicorn app.main:app --host 127.0.0.1 --port 8000")
        return 1

    import os
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        default_browsers = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        if default_browsers.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(default_browsers)

    OUT.mkdir(exist_ok=True)
    shots = OUT / "screenshots"
    shots.mkdir(exist_ok=True)
    raw = OUT / "_raw"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir()

    total_ms = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(raw),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto(URL, wait_until="networkidle")

        page.wait_for_function("document.querySelectorAll('.slide').length > 0")
        slide_count = page.locator(".slide").count()

        for i in range(slide_count):
            page.wait_for_function(
                f"document.querySelectorAll('.slide')[{i}].classList.contains('active')"
            )
            dur = page.locator(".slide").nth(i).get_attribute("data-duration")
            wait_s = (int(dur or 3500) + 400) / 1000
            time.sleep(wait_s)
            page.screenshot(path=str(shots / f"{i + 1:02d}-slide.png"))

        page.wait_for_function("document.getElementById('stage').dataset.done === '1'", timeout=120_000)
        time.sleep(0.8)

        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()

    mp4 = OUT / "pandabook-overview.mp4"
    if video_path and Path(video_path).exists():
        shutil.move(str(video_path), str(mp4))
        print(f"Video: {mp4}")
    else:
        print("Video file not found — check playwright record_video_dir")

    if raw.exists():
        shutil.rmtree(raw, ignore_errors=True)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and list(shots.glob("*.png")):
        slideshow = OUT / "pandabook-slideshow.mp4"
        cmd = [
            ffmpeg, "-y",
            "-framerate", "1/3",
            "-i", str(shots / "%02d-slide.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1280:720",
            str(slideshow),
        ]
        # rename pattern: ffmpeg needs sequential 01,02 — our files are 01-slide.png
        # use concat demuxer instead
        list_file = OUT / "ffmpeg-list.txt"
        lines = []
        for png in sorted(shots.glob("*-slide.png")):
            lines.append(f"file '{png.as_posix()}'")
            lines.append("duration 3")
        if lines:
            lines.append(f"file '{sorted(shots.glob('*-slide.png'))[-1].as_posix()}'")
            list_file.write_text("\n".join(lines), encoding="utf-8")
            subprocess.run(
                [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-vf", "scale=1280:720", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(slideshow)],
                check=False,
            )
            print(f"Slideshow: {slideshow}")

    print(f"Screenshots: {shots}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
