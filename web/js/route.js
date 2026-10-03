// Hash-route parsing and matching. Pure (no DOM), unit-tested in web/tests/.
// Routes look like "#/feature/receipt?tab=data". Patterns use ":name" segments.

export function parseHash(hash) {
  const raw = String(hash || "").replace(/^#/, "") || "/";
  const [pathPart, queryPart = ""] = raw.split("?", 2);
  const path = "/" + pathPart.split("/").filter(Boolean).map(decodeURIComponent).join("/");
  const query = Object.fromEntries(new URLSearchParams(queryPart));
  return { path, query };
}

export function matchRoute(pattern, path) {
  const want = pattern.split("/").filter(Boolean);
  const have = path.split("/").filter(Boolean);
  if (want.length !== have.length) return null;
  const params = {};
  for (let i = 0; i < want.length; i += 1) {
    if (want[i].startsWith(":")) params[want[i].slice(1)] = have[i];
    else if (want[i] !== have[i]) return null;
  }
  return params;
}

/** First route whose pattern matches, with its params; null if none. */
export function resolve(routes, hash) {
  const { path, query } = parseHash(hash);
  for (const route of routes) {
    const params = matchRoute(route.path, path);
    if (params) return { route, params, query, path };
  }
  return null;
}

export function href(path, query = {}) {
  const qs = new URLSearchParams(query).toString();
  return `#${path}${qs ? `?${qs}` : ""}`;
}
