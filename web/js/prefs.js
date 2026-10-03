// Per-browser preferences (theme, provider override). localStorage can be blocked
// (private windows, file://), so every access is guarded and the app works without it.

const KEY = "hackkit.prefs";

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch {
    return {};
  }
}

export function get(name, fallback = null) {
  const value = readAll()[name];
  return value === undefined ? fallback : value;
}

export function set(name, value) {
  try {
    const all = readAll();
    if (value === null || value === undefined) delete all[name];
    else all[name] = value;
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable: preference lasts for this page view only */
  }
}
