"""Browser steps shared by scripts/shots.py and scripts/demo_video.py (Playwright, sync API).

A step is one TOML inline table. Supported keys (one action per step):

    {goto = "#/feature/receipt"}           open a route (waits until the app is ready)
    {click = "#run"}                       click a CSS selector or "text=Run"
    {fill = "#input-text", text = "..."}   replace the value of an input
    {type = "#input-text", text = "...", delay = 35}   type like a human (good for videos)
    {press = "Control+Enter"}              keyboard shortcut
    {hover = ".metric"}                    move the mouse over an element
    {wait_for = "text=Needs human review"} wait until something is visible
    {wait = 800}                           pause, in milliseconds
    {scroll_to = "#how"}                   scroll an element into view
    {scroll = 600}                         scroll the page by N pixels
    {theme = "light"}                      switch the app theme
    {caption = "Text"}                     (video) subtitle at the bottom; "" hides it
    {title = "Name", subtitle = "...", seconds = 2.5}   (video) full-screen title card
    {highlight = ".metric", seconds = 1.5}  (video) draw a ring around an element

Video-only steps are ignored when taking screenshots.
"""

from __future__ import annotations

import contextlib
from typing import Any

VIDEO_ONLY = {"caption", "title", "highlight"}

# Injected into every page during recordings: a visible cursor, subtitles, title cards and
# highlight rings (headless video has no cursor, and silent videos need captions).
OVERLAY_JS = r"""
(() => {
  if (window.__hk_overlay) return;
  window.__hk_overlay = true;
  const css = document.createElement("style");
  css.textContent = `
    #hk-cursor { position: fixed; z-index: 2147483647; width: 22px; height: 22px; margin: -11px 0 0 -11px;
      border-radius: 50%; background: rgba(255,255,255,.85); border: 2px solid rgba(0,0,0,.6);
      box-shadow: 0 0 0 6px rgba(45,212,191,.35); pointer-events: none; transition: transform .12s; }
    #hk-cursor.down { transform: scale(.7); }
    #hk-caption { position: fixed; z-index: 2147483646; left: 50%; bottom: 44px; transform: translateX(-50%);
      max-width: min(80vw, 1100px); padding: 14px 24px; border-radius: 14px; background: rgba(5,12,14,.88);
      color: #fff; font: 600 26px/1.35 Inter, system-ui, sans-serif; text-align: center;
      box-shadow: 0 10px 40px rgba(0,0,0,.5); pointer-events: none; }
    #hk-title { position: fixed; inset: 0; z-index: 2147483647; display: grid; place-content: center; gap: 18px;
      text-align: center; background: radial-gradient(1200px 600px at 50% 0%, rgba(45,212,191,.25), transparent 60%), #071013;
      color: #fff; font-family: Inter, system-ui, sans-serif; pointer-events: none; }
    #hk-title h1 { margin: 0; font-size: 84px; letter-spacing: -.03em; }
    #hk-title p { margin: 0; font-size: 30px; color: #92a9b0; }
    .hk-ring { position: fixed; z-index: 2147483645; border: 3px solid #f59e0b; border-radius: 14px;
      box-shadow: 0 0 0 9999px rgba(0,0,0,.35); pointer-events: none; transition: all .3s; }`;
  document.head.append(css);
  const cursor = document.createElement("div");
  cursor.id = "hk-cursor";
  document.addEventListener("mousemove", (e) => {
    if (!cursor.isConnected) document.body.append(cursor);
    cursor.style.left = e.clientX + "px";
    cursor.style.top = e.clientY + "px";
  }, true);
  document.addEventListener("mousedown", () => cursor.classList.add("down"), true);
  document.addEventListener("mouseup", () => cursor.classList.remove("down"), true);
  window.__hk_caption = (text) => {
    let box = document.getElementById("hk-caption");
    if (!text) { box?.remove(); return; }
    if (!box) { box = document.createElement("div"); box.id = "hk-caption"; document.body.append(box); }
    box.textContent = text;
  };
  window.__hk_title = (title, subtitle) => {
    document.getElementById("hk-title")?.remove();
    if (!title) return;
    const card = document.createElement("div");
    card.id = "hk-title";
    const h = document.createElement("h1"); h.textContent = title;
    const p = document.createElement("p"); p.textContent = subtitle || "";
    card.append(h, p);
    document.body.append(card);
  };
  window.__hk_ring = (selector) => {
    document.querySelectorAll(".hk-ring").forEach((n) => n.remove());
    if (!selector) return;
    const el = document.querySelector(selector);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const ring = document.createElement("div");
    ring.className = "hk-ring";
    Object.assign(ring.style, { left: r.left - 8 + "px", top: r.top - 8 + "px", width: r.width + 16 + "px", height: r.height + 16 + "px" });
    document.body.append(ring);
  };
})();
"""


class StepError(RuntimeError):
    pass


def theme_init_script(theme: str) -> str:
    """Init script that stores the app theme before the page loads (no light/dark flash)."""
    return (
        "try { const p = JSON.parse(localStorage.getItem('hackkit.prefs') || '{}');"
        f" p.theme = {theme!r};"
        " localStorage.setItem('hackkit.prefs', JSON.stringify(p)); } catch (e) {}"
    )


def wait_ready(page: Any, timeout_ms: int = 15000) -> None:
    """The app sets <html data-ready="true"> after the first render (web/js/app.js)."""
    page.wait_for_selector("html[data-ready=true]", timeout=timeout_ms)
    # Maps keep fetching tiles, so "network idle" may never come; readiness is enough.
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=4000)
    page.wait_for_timeout(350)  # let fade-in animations finish


def goto(page: Any, base: str, route: str) -> None:
    route = route if route.startswith(("#", "?", "/")) else f"#/{route}"
    url = f"{base}/{route.lstrip('/')}" if not route.startswith("http") else route
    if page.url == url:
        page.reload()  # same route again: force a fresh render
    elif page.url.split("#", 1)[0] == url.split("#", 1)[0] and "#" in url:
        # Same document, new hash: the app re-renders without a reload.
        page.evaluate(
            "(h) => { document.documentElement.removeAttribute('data-ready'); location.hash = h; }",
            "#" + url.split("#", 1)[1],
        )
    else:
        page.goto(url)
    wait_ready(page)


def _move_to(page: Any, selector: str, steps: int = 18) -> None:
    box = page.locator(selector).first.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)


def run_step(page: Any, base: str, step: dict[str, Any], *, video: bool = False) -> None:
    """Run one step. Raises StepError with the step text when it fails."""
    action = next((k for k in step if k not in {"text", "delay", "seconds", "subtitle"}), None)
    if action is None:
        raise StepError(f"step has no action: {step}")
    if action in VIDEO_ONLY and not video:
        return
    try:
        if action == "goto":
            goto(page, base, step["goto"])
            if video:
                page.evaluate(OVERLAY_JS)
        elif action == "click":
            if video:
                _move_to(page, step["click"])
            page.locator(step["click"]).first.click()
        elif action == "fill":
            page.locator(step["fill"]).first.fill(step.get("text", ""))
        elif action == "type":
            target = page.locator(step["type"]).first
            if video:
                _move_to(page, step["type"])
            target.click()
            target.fill("")
            target.press_sequentially(step.get("text", ""), delay=step.get("delay", 35))
        elif action == "press":
            page.keyboard.press(step["press"])
        elif action == "hover":
            if video:
                _move_to(page, step["hover"], steps=24)
            page.locator(step["hover"]).first.hover()
        elif action == "wait_for":
            page.locator(step["wait_for"]).first.wait_for(state="visible")
            page.wait_for_timeout(300)
        elif action == "wait":
            page.wait_for_timeout(int(step["wait"]))
        elif action == "scroll_to":
            page.locator(step["scroll_to"]).first.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
        elif action == "scroll":
            page.mouse.wheel(0, int(step["scroll"]))
            page.wait_for_timeout(500)
        elif action == "theme":
            page.evaluate(
                "(t) => { const p = JSON.parse(localStorage.getItem('hackkit.prefs') || '{}');"
                " p.theme = t; localStorage.setItem('hackkit.prefs', JSON.stringify(p));"
                " document.documentElement.dataset.theme = t; }",
                step["theme"],
            )
        elif action == "caption":
            page.evaluate("(t) => window.__hk_caption && window.__hk_caption(t)", step["caption"])
        elif action == "title":
            page.evaluate(
                "([t, s]) => window.__hk_title && window.__hk_title(t, s)",
                [step["title"], step.get("subtitle", "")],
            )
            page.wait_for_timeout(int(float(step.get("seconds", 2.5)) * 1000))
            page.evaluate("() => window.__hk_title && window.__hk_title('')")
        elif action == "highlight":
            page.evaluate("(s) => window.__hk_ring && window.__hk_ring(s)", step["highlight"])
            page.wait_for_timeout(int(float(step.get("seconds", 1.5)) * 1000))
            page.evaluate("() => window.__hk_ring && window.__hk_ring('')")
        else:
            raise StepError(f"unknown action {action!r} in {step}")
    except StepError:
        raise
    except Exception as exc:  # noqa: BLE001 - report which step broke, in plain words
        raise StepError(f"step {step} failed: {str(exc).splitlines()[0]}") from exc


def console_watch(page: Any, sink: list[str]) -> None:
    """Collect browser errors (page crashes and console.error) into `sink`."""
    page.on("pageerror", lambda exc: sink.append(f"page error: {exc}"))
    page.on(
        "console",
        lambda msg: msg.type == "error" and sink.append(f"console.error: {msg.text[:300]}"),
    )
