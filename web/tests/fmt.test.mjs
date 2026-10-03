import { test } from "node:test";
import assert from "node:assert/strict";
import * as fmt from "../js/fmt.js";

test("money uses cents below 1000 and whole dollars above", () => {
  assert.equal(fmt.money(24.6), "$24.60");
  assert.equal(fmt.money(235406.4), "$235,406");
  assert.equal(fmt.money(null), "—");
});

test("pct accepts fractions and percents", () => {
  assert.equal(fmt.pct(0.256), "25.6%");
  assert.equal(fmt.pct(0.35, 0), "35%");
  assert.equal(fmt.pct(12.5), "12.5%");
});

test("metric picks a format from the key", () => {
  assert.equal(fmt.metric("computed_total", 24.64), "$24.64");
  assert.equal(fmt.metric("margin_pct", 0.35), "35%");
  assert.equal(fmt.metric("item_count", 3), "3");
  assert.equal(fmt.metric("ok", true), "Yes");
});

test("humanize turns keys into labels", () => {
  assert.equal(fmt.humanize("computed_total"), "Computed total");
  assert.equal(fmt.humanize("co2Tons"), "Co2 tons");
});

test("display handles every JSON type", () => {
  assert.equal(fmt.display(null), "—");
  assert.equal(fmt.display([1, 2]), "1, 2");
  assert.equal(fmt.display(1234.5), "1,235");
  assert.equal(fmt.display({ a: 1 }), '{"a":1}');
});
