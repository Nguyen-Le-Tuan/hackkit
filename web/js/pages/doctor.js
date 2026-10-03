// #/doctor — open this on the DEMO laptop's browser before you present. It checks what the
// terminal cannot: WebGL (3D maps), fonts, screen size, the API, and offline readiness.

import * as api from "../api.js";
import * as fmt from "../fmt.js";
import { h, mount, button, badge, card, table, callout } from "../ui.js";

function webgl() {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return ["FAIL", "No WebGL: 3D maps fall back to a flat SVG map. Enable hardware acceleration in the browser settings."];
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : "unknown GPU";
    const soft = /swiftshader|llvmpipe|software/i.test(renderer);
    return [soft ? "WARN" : "OK", `${gl instanceof WebGL2RenderingContext ? "WebGL 2" : "WebGL 1"} on ${renderer}${soft ? " (software rendering: maps may be slow)" : ""}`];
  } catch (error) {
    return ["FAIL", `WebGL check crashed: ${error.message}`];
  }
}

async function apiCheck() {
  const started = performance.now();
  const mode = api.mode();
  if (mode === "live") {
    try {
      await api.features();
      const info = api.health();
      return ["OK", `Live server, provider "${info.provider}"${info.demo_mode ? ", DEMO MODE on" : ""}, ${fmt.duration(performance.now() - started)}`];
    } catch (error) {
      return ["FAIL", error.message];
    }
  }
  if (mode === "static") return ["WARN", "Static snapshot (no server). Fine for GitHub Pages; run `make run` for live model calls."];
  return ["FAIL", "No server and no snapshot. Run `make run`, or `make snapshot` for an offline copy."];
}

async function snapshotCheck() {
  try {
    const response = await fetch("snapshots/index.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const index = await response.json();
    const runs = Object.values(index.runs || {}).reduce((a, b) => a + b, 0);
    const provider = index.provider === "fake" ? " (made with the FAKE provider: re-run with the real model)" : "";
    return [index.provider === "fake" ? "WARN" : "OK", `${runs} saved run(s), ${index.generated_at}${provider}`];
  } catch {
    return ["WARN", "No web/snapshots: if Wi-Fi or the server dies there is nothing to fall back to. Run `make snapshot`."];
  }
}

function fontCheck() {
  const ok = document.fonts?.check?.('600 16px "Inter"');
  return ok ? ["OK", "Inter loaded"] : ["WARN", "Inter not loaded (offline?): the system font is used instead; layout still works."];
}

function screenCheck() {
  const w = window.innerWidth;
  const hgt = window.innerHeight;
  const dpr = window.devicePixelRatio;
  const status = w < 1200 ? "WARN" : "OK";
  return [status, `${w}×${hgt} viewport, devicePixelRatio ${dpr}${w < 1200 ? ": narrow for a projector; zoom out (Ctrl -) or go full screen (F11)" : ""}`];
}

function storageCheck() {
  try {
    localStorage.setItem("hackkit.doctor", "1");
    localStorage.removeItem("hackkit.doctor");
    return ["OK", "localStorage works"];
  } catch {
    return ["WARN", "localStorage blocked (private window?): preferences will not persist."];
  }
}

export async function render() {
  const out = h("div");
  const runAll = async () => {
    mount(out, h("p", { class: "faint" }, "Checking…"));
    const rows = [
      ["API", ...(await apiCheck())],
      ["Offline snapshot", ...(await snapshotCheck())],
      ["WebGL (3D maps)", ...webgl()],
      ["Fonts", ...fontCheck()],
      ["Screen", ...screenCheck()],
      ["Network", navigator.onLine ? "OK" : "WARN", navigator.onLine ? "Online" : "Offline: CDN maps/charts fall back to SVG"],
      ["Storage", ...storageCheck()],
      ["Browser", "INFO", navigator.userAgent],
    ].map(([check, status, detail]) => ({ check, status, detail }));
    const failed = rows.filter((r) => r.status === "FAIL").length;
    const warned = rows.filter((r) => r.status === "WARN").length;
    mount(
      out,
      failed ? callout("bad", `${failed} problem(s) to fix before the demo.`) : warned ? callout("warn", `Ready, with ${warned} warning(s).`) : callout("good", "This browser is ready for the demo."),
      h("div", { style: { marginTop: "16px" } }, table(rows, [
        { key: "check", label: "Check" },
        { key: "status", label: "Status", format: (v) => badge(v, { OK: "good", WARN: "warn", FAIL: "bad", INFO: "info" }[v]) },
        { key: "detail", label: "Detail" },
      ])),
    );
  };
  queueMicrotask(runAll);
  return h(
    "div",
    { class: "page fade-in" },
    h("header", { class: "page-head" }, h("div", {}, h("div", { class: "eyebrow" }, "Demo machine"), h("h1", {}, "Doctor"), h("p", { class: "lede" }, "Open this page in the browser you will present with. Run `make doctor` in the terminal too.")), button("Check again", { onClick: runAll })),
    card({}, out),
  );
}
