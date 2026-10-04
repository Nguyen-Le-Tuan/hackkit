"""Record the demo video from a script: `make demo-video`.

Reads docs/pitch/demo_flow.toml (title cards, captions, clicks, typing, highlights), drives the
real app in headless Chromium, records it, and converts it to MP4 with ffmpeg when available.
The video has a visible cursor and burned-in captions, so it works with no voice-over: upload
it to YouTube (unlisted) for Devpost, and keep it on the demo laptop as the backup.

    make demo-video                    # docs/pitch/out/demo.mp4 (+ .webm)
    python scripts/demo_video.py --base http://localhost:8000   # record a running app

Setup once: pip install -e ".[pitch]" && playwright install chromium   (ffmpeg for MP4)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import browser_steps  # noqa: E402
from appserver import ROOT, app_server  # noqa: E402

CONFIG = ROOT / "docs" / "pitch" / "demo_flow.toml"
OUT = ROOT / "docs" / "pitch" / "out"


def to_mp4(webm: Path, mp4: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    command = [
        ffmpeg, "-y", "-loglevel", "error", "-i", str(webm),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(mp4),
    ]  # fmt: skip
    return subprocess.run(command, check=False).returncode == 0


def duration_s(video: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def record(base: str, flow: dict, out: Path) -> int:
    from playwright.sync_api import sync_playwright

    video = flow.get("video", {})
    width, _, height = str(video.get("viewport", "1600x900")).partition("x")
    size = {"width": int(width), "height": int(height)}
    vw, _, vh = str(video.get("size", "1920x1080")).partition("x")
    theme = video.get("theme", "dark")
    name = video.get("name", "demo")
    steps = flow.get("step", [])
    if not steps:
        print(f"No [[step]] in {CONFIG}")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport=size,
            record_video_dir=tmp,
            record_video_size={"width": int(vw), "height": int(vh)},
        )
        context.add_init_script(browser_steps.theme_init_script(theme))
        context.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => {"
            + browser_steps.OVERLAY_JS
            + "});"
        )
        page = context.new_page()
        page.set_default_timeout(10_000)  # a missing button fails fast, naming the step
        browser_steps.console_watch(page, errors)
        failed = None
        for number, step in enumerate(steps, start=1):
            try:
                browser_steps.run_step(page, base, step, video=True)
            except browser_steps.StepError as exc:
                failed = f"step {number}: {exc}"
                break
        page.wait_for_timeout(int(float(video.get("tail_seconds", 1.5)) * 1000))
        recorded = Path(page.video.path())
        context.close()
        browser.close()
        webm = out / f"{name}.webm"
        shutil.move(str(recorded), webm)

    print(f"  recorded {webm.relative_to(ROOT)} in {time.monotonic() - started:.0f}s")
    final = webm
    mp4 = out / f"{name}.mp4"
    if to_mp4(webm, mp4):
        final = mp4
        print(f"  converted {mp4.relative_to(ROOT)}")
    else:
        print("  ffmpeg not found: keeping the .webm (YouTube and Devpost accept it)")
    seconds = duration_s(final)
    limit = float(video.get("max_seconds", 180))
    if seconds is not None:
        verdict = "OK" if seconds <= limit else f"TOO LONG (limit {limit:.0f}s)"
        print(f"  length {seconds:.0f}s: {verdict}")
    for error in errors:
        print(f"  PROBLEM {error}")
    if failed:
        print(f"  PROBLEM {failed}")
        return 1
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the demo video from a script.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--base", default=None, help="URL of a running app (default: start one)")
    args = parser.parse_args(argv)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print('Playwright missing: pip install -e ".[pitch]" && playwright install chromium')
        return 2
    flow = tomllib.loads(args.config.read_text(encoding="utf-8"))
    with app_server(args.base) as base:
        return record(base, flow, args.out)


if __name__ == "__main__":
    sys.exit(main())
