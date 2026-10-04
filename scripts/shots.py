"""Screenshots of the real app for slides, README and Devpost: `make shots`.

Reads docs/pitch/shots.toml, starts the app on a free port (or uses --base), runs each shot's
steps in headless Chromium and saves PNGs to docs/pitch/shots/. Fails when the page logs an
error, so a broken page never ends up in the slides.

    make shots                       # every shot in docs/pitch/shots.toml
    make shots ONLY=home             # one shot
    python scripts/shots.py --smoke  # CI: open every route, check for errors, save nothing
    python scripts/shots.py --base http://localhost:8000   # use a server that is running

Setup once: pip install -e ".[pitch]" && playwright install chromium
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import browser_steps  # noqa: E402
from appserver import ROOT, app_server  # noqa: E402

CONFIG = ROOT / "docs" / "pitch" / "shots.toml"
DEFAULT_SMOKE_ROUTES = ["#/", "#/kit", "#/doctor"]
STEP_TIMEOUT_MS = 10_000  # a missing button fails fast with the step in the message


def parse_size(text: str) -> tuple[int, int]:
    width, _, height = text.lower().partition("x")
    return int(width), int(height)


def load_shots(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    shots = data.get("shot", [])
    names = [s.get("name") for s in shots]
    if any(not n for n in names):
        raise SystemExit(f"{path}: every [[shot]] needs a name")
    if len(names) != len(set(names)):
        raise SystemExit(f"{path}: shot names must be unique")
    return defaults, shots


def output_name(name: str, size: str, sizes: list[str]) -> str:
    return f"{name}.png" if len(sizes) == 1 else f"{name}@{size}.png"


def take(base: str, defaults: dict[str, Any], shots: list[dict[str, Any]], out: Path) -> int:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    saved = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for shot in shots:
            sizes = shot.get("sizes", defaults.get("sizes", ["1440x900"]))
            theme = shot.get("theme", defaults.get("theme", "dark"))
            scale = shot.get("scale", defaults.get("scale", 2))
            for size in sizes:
                width, height = parse_size(size)
                context = browser.new_context(
                    viewport={"width": width, "height": height}, device_scale_factor=scale
                )
                context.add_init_script(browser_steps.theme_init_script(theme))
                page = context.new_page()
                page.set_default_timeout(STEP_TIMEOUT_MS)
                errors: list[str] = []
                browser_steps.console_watch(page, errors)
                try:
                    browser_steps.goto(page, base, shot.get("route", "#/"))
                    for step in shot.get("steps", []):
                        browser_steps.run_step(page, base, step)
                    page.wait_for_timeout(
                        int(shot.get("settle_ms", defaults.get("settle_ms", 400)))
                    )
                    target = out / output_name(shot["name"], size, sizes)
                    if shot.get("selector"):
                        # The sticky top bar would cover the element once it is scrolled to.
                        page.add_style_tag(content=".topbar { position: static !important; }")
                        page.locator(shot["selector"]).first.screenshot(path=str(target))
                    else:
                        page.screenshot(
                            path=str(target),
                            full_page=shot.get("full_page", defaults.get("full_page", False)),
                        )
                    saved += 1
                    print(f"  saved {target.relative_to(ROOT)}")
                except browser_steps.StepError as exc:
                    problems.append(f"{shot['name']} @ {size}: {exc}")
                finally:
                    context.close()
                problems += [f"{shot['name']} @ {size}: {e}" for e in errors]
        browser.close()
    for problem in problems:
        print(f"  PROBLEM {problem}")
    print(f"shots: {saved} saved to {out.relative_to(ROOT)}, {len(problems)} problem(s)")
    return 1 if problems else 0


def smoke(base: str, routes: list[str]) -> int:
    """Open each route at desktop and phone size; fail on any browser error."""
    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    checked = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in ((1440, 900), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_default_timeout(STEP_TIMEOUT_MS)
            errors: list[str] = []
            browser_steps.console_watch(page, errors)
            # Every page in the top bar is checked too (custom pages added during the event).
            browser_steps.goto(page, base, "#/")
            nav = page.eval_on_selector_all(".nav a", "els => els.map(a => a.getAttribute('href'))")
            for route in dict.fromkeys([*routes, *nav]):
                try:
                    browser_steps.goto(page, base, route)
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth - window.innerWidth"
                    )
                    if overflow > 2:
                        problems.append(
                            f"{route} @ {width}px: page scrolls sideways by {overflow}px"
                        )
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{route} @ {width}px: {str(exc).splitlines()[0]}")
            problems += [f"@ {width}px: {e}" for e in errors]
            checked = len(dict.fromkeys([*routes, *nav]))
            page.close()
        browser.close()
    for problem in problems:
        print(f"  PROBLEM {problem}")
    print(f"smoke: {checked} route(s) x 2 sizes, {len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screenshots of the real app.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=None, help="default: next to the config")
    parser.add_argument("--only", default="", help="comma-separated shot names")
    parser.add_argument("--base", default=None, help="URL of a running app (default: start one)")
    parser.add_argument("--smoke", action="store_true", help="check routes for errors only")
    parser.add_argument("--route", action="append", default=[], help="extra route for --smoke")
    args = parser.parse_args(argv)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print('Playwright missing: pip install -e ".[pitch]" && playwright install chromium')
        return 2

    with app_server(args.base) as base:
        if args.smoke:
            routes = list(DEFAULT_SMOKE_ROUTES)
            if args.config.exists():
                _, shots = load_shots(args.config)
                routes += [s.get("route", "#/") for s in shots]
            return smoke(base, list(dict.fromkeys(routes + args.route)))
        defaults, shots = load_shots(args.config)
        if args.only:
            wanted = {n.strip() for n in args.only.split(",")}
            shots = [s for s in shots if s["name"] in wanted]
            if not shots:
                print(f"No shot named {args.only!r} in {args.config}")
                return 2
        out = args.out or args.config.parent / "shots"
        return take(base, defaults, shots, out)


if __name__ == "__main__":
    sys.exit(main())
