// One API client, two backends:
//   live   -> the FastAPI server (make run): POST api/run/<key>, GET api/...
//   static -> files written by `make snapshot` in web/snapshots/ (GitHub Pages, no Wi-Fi)
// Pages never care which one is active. Add ?static=1 to the URL to force static mode.
// URLs are relative on purpose, so the app works at "/" and under "/<repo>/" on GitHub Pages.

import { snapshotName } from "./snapshot-name.js";
import * as prefs from "./prefs.js";

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.status = status;
  }
}

const state = { mode: "unknown", health: null, cache: new Map() };

async function fetchJSON(url, { method = "GET", body, timeout = 60000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (!response.ok) {
      const detail = data && (data.detail ?? data.message);
      throw new ApiError(typeof detail === "string" ? detail : `HTTP ${response.status} for ${url}`, response.status);
    }
    if (data === null) throw new ApiError(`Not JSON: ${url}`, response.status);
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new ApiError(`Timed out after ${timeout / 1000}s: ${url}`);
    if (error instanceof ApiError) throw error;
    throw new ApiError(`Network error for ${url}: ${error.message}`);
  } finally {
    clearTimeout(timer);
  }
}

async function cached(url) {
  if (!state.cache.has(url)) state.cache.set(url, fetchJSON(url, { timeout: 8000 }));
  try {
    return await state.cache.get(url);
  } catch (error) {
    state.cache.delete(url);
    throw error;
  }
}

/** Decide live vs static once, at boot. Never throws. */
export async function init({ forceStatic = false } = {}) {
  if (!forceStatic) {
    try {
      state.health = await fetchJSON("api/health", { timeout: 2500 });
      state.mode = "live";
      return state.mode;
    } catch {
      /* fall through to static */
    }
  }
  try {
    state.health = await cached("snapshots/health.json");
    state.mode = "static";
  } catch {
    state.health = null;
    state.mode = "offline";
  }
  return state.mode;
}

export const mode = () => state.mode;
export const health = () => state.health;

export async function features() {
  if (state.mode === "live") return cached("api/features");
  if (state.mode === "static") return cached("snapshots/features.json");
  return [];
}

export async function feature(key) {
  const list = await features();
  const found = list.find((f) => f.key === key);
  if (!found) throw new ApiError(`No feature named "${key}".`, 404);
  return found;
}

/** Run a feature. body = {text, attachments:[{media_type, data_b64, name}]}. */
export async function run(key, body) {
  if (state.mode === "live") {
    const overrides = {};
    const provider = prefs.get("provider");
    const demo = prefs.get("demo_mode");
    if (provider) overrides.provider = provider;
    if (demo !== null) overrides.demo_mode = demo;
    return fetchJSON(`api/run/${encodeURIComponent(key)}`, { method: "POST", body: { ...body, ...overrides } });
  }
  if (state.mode === "static") {
    const saved = await cached(`snapshots/runs/${encodeURIComponent(key)}.json`);
    if (!saved.length) throw new ApiError(`No saved runs for "${key}". Run make snapshot.`);
    const text = (body.text || "").trim();
    const exact = saved.find((entry) => entry.text.trim() === text);
    const entry = exact || saved[0];
    return { ...entry.result, static: true, static_input_matched: Boolean(exact), static_input: entry.text };
  }
  throw new ApiError("No server and no saved snapshot. Start the app with make run.");
}

/** GET any /api path; in static mode reads the file `make snapshot` saved for it. */
export async function get(path) {
  const clean = path.replace(/^\//, "");
  if (state.mode === "live") return fetchJSON(clean.startsWith("api/") ? clean : `api/${clean}`);
  if (state.mode === "static") return cached(`snapshots/api/${snapshotName(path)}.json`);
  throw new ApiError("No server and no saved snapshot.");
}

export async function post(path, body) {
  if (state.mode !== "live") throw new ApiError("This action needs the live server (make run).");
  const clean = path.replace(/^\//, "");
  return fetchJSON(clean.startsWith("api/") ? clean : `api/${clean}`, { method: "POST", body });
}

export async function clearCache() {
  return post("api/cache/clear", {});
}
