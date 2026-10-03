import { test } from "node:test";
import assert from "node:assert/strict";
import { parseHash, matchRoute, resolve, href } from "../js/route.js";

test("parseHash splits path and query", () => {
  assert.deepEqual(parseHash("#/feature/receipt?tab=data"), { path: "/feature/receipt", query: { tab: "data" } });
  assert.deepEqual(parseHash(""), { path: "/", query: {} });
  assert.deepEqual(parseHash("#/a//b/"), { path: "/a/b", query: {} });
});

test("matchRoute binds params", () => {
  assert.deepEqual(matchRoute("/feature/:key", "/feature/receipt"), { key: "receipt" });
  assert.equal(matchRoute("/feature/:key", "/feature"), null);
  assert.deepEqual(matchRoute("/", "/"), {});
});

test("resolve returns the first match", () => {
  const routes = [{ path: "/feature/receipt" }, { path: "/feature/:key" }];
  assert.equal(resolve(routes, "#/feature/receipt").route, routes[0]);
  assert.equal(resolve(routes, "#/feature/other").params.key, "other");
  assert.equal(resolve(routes, "#/nope"), null);
  assert.equal(href("/feature/x", { a: "1" }), "#/feature/x?a=1");
});
