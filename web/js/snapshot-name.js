// Same rule as hackkit.snapshot.snapshot_name in Python: "/api/x/top?n=10&a=b" -> "x__top__a-b_n-10".
// Keep the two in sync; web/tests/snapshot-name.test.mjs checks the shared examples.

export function snapshotName(path) {
  const [rawRoute, rawQuery = ""] = String(path).split("?", 2);
  let route = rawRoute.startsWith("/") ? rawRoute.slice(1) : rawRoute;
  if (route.startsWith("api/")) route = route.slice(4);
  let name = route.split("/").filter(Boolean).join("__") || "root";
  const pairs = new URLSearchParams(rawQuery);
  const query = [...pairs.entries()].sort((a, b) =>
    a[0] === b[0] ? (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0) : a[0] < b[0] ? -1 : 1,
  );
  if (query.length) name += "__" + query.map(([k, v]) => `${k}-${v}`).join("_");
  return name.replace(/[^A-Za-z0-9._-]/g, "-");
}
