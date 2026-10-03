// #/kit — every UI component with sample data. Copy from here when building a page; `make shots`
// also captures it, so a CSS change that breaks a component shows up in review.

import * as fmt from "../fmt.js";
import { createChart } from "../chart.js";
import { createMap } from "../map.js";
import {
  h, icon, iconNames, button, linkButton, badge, chip, source, demoBadge, card, metricTile, metrics, callout, kv,
  table, tabs, codeBlock, disclosure, skeleton, spinner, emptyState, errorState, toast, drawer, dropzone,
} from "../ui.js";

const SAMPLE_ROWS = [
  { name: "Seneca One", floors: 40, savings_usd: 235406, confidence: 0.9 },
  { name: "532 Main St", floors: 12, savings_usd: 99917, confidence: 0.8 },
  { name: "107 Delaware Ave", floors: 9, savings_usd: 60840, confidence: 0.7 },
];

const SAMPLE_GEOJSON = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { name: "Point A", value: 120, height_m: 40 }, geometry: { type: "Polygon", coordinates: [[[-78.8785, 42.8865], [-78.8775, 42.8865], [-78.8775, 42.8872], [-78.8785, 42.8872], [-78.8785, 42.8865]]] } },
    { type: "Feature", properties: { name: "Point B", value: 300, height_m: 90 }, geometry: { type: "Polygon", coordinates: [[[-78.8768, 42.8858], [-78.8756, 42.8858], [-78.8756, 42.8868], [-78.8768, 42.8868], [-78.8768, 42.8858]]] } },
    { type: "Feature", properties: { name: "Station C", value: 80 }, geometry: { type: "Point", coordinates: [-78.8795, 42.8852] } },
  ],
};

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function section(title, ...body) {
  return h("section", { class: "section" }, h("h2", {}, title), body);
}

export async function render() {
  const mapEl = h("div", { class: "map", style: { height: "380px" } });
  const chartEl = h("div", { class: "chart" });
  const page = h(
    "div",
    { class: "page fade-in" },
    h("header", { class: "page-head" }, h("div", {}, h("div", { class: "eyebrow" }, "UI kit"), h("h1", {}, "Components"), h("p", { class: "lede" }, "Everything in web/js/ui.js and web/css/components.css. Build pages from these; do not add a CSS framework."))),
    section(
      "Buttons and badges",
      h("div", { class: "stack" },
        h("div", { class: "row" }, button("Primary", { kind: "primary", iconName: "play" }), button("Default"), button("Ghost", { kind: "ghost" }), button("Small", { size: "sm" }), button("Large", { kind: "primary", size: "lg" }), button("Disabled", { disabled: true }), linkButton("Link button", "#/kit", { iconName: "link" })),
        h("div", { class: "row" }, badge("default"), badge("good", "good"), badge("warn", "warn"), badge("bad", "bad"), badge("info", "info"), badge("accent", "accent"), demoBadge(), chip("Live"), chip("Static", "warn"), chip("Offline", "bad")),
        h("div", { class: "row" }, h("span", {}, "Footprint 12,400 sq ft "), source("OpenStreetMap", 0.9, "way 1234"), h("span", {}, " Cost "), h("span", { class: "demo-value" }, "$8/sq ft"), demoBadge()),
        h("div", { class: "row faint" }, iconNames.map((name) => h("span", { title: name }, icon(name, 20)))),
      ),
    ),
    section(
      "Metrics",
      metrics([
        metricTile("Annual savings", fmt.money(235406), { foot: source("NOCO calculator") }),
        metricTile("Incentive", fmt.money(150000), { foot: h("span", {}, "capped") }),
        metricTile("Payback", "10.8 yrs", { demo: true }),
        metricTile("Needs review", "2", { warn: true }),
      ]),
    ),
    section(
      "Callouts",
      h("div", { class: "stack tight" }, callout("good", "Checks passed.", "Items add up to the printed total."), callout("warn", "Stated total.", "Items add up to 24.56 but the receipt says 24.60."), callout("bad", "Could not read the file.", "The PDF has no text layer."), callout("info", "Offline mode.", "Showing saved results."), callout("demo", "Red = DEMO value.", "Not from the partner or public data.")),
    ),
    section(
      "Cards, key/value, tabs",
      h("div", { class: "grid cols-2" },
        card({ title: "Card with actions", actions: button("Action", { size: "sm" }) }, kv([["Address", "33 Franklin St"], ["Floors", 11], ["Use", "Office"], ["Source", source("Buffalo roll", 0.7)]])),
        card({ title: "Tabs" }, tabs([{ label: "One", content: h("p", {}, "First panel.") }, { label: "Two", content: codeBlock('{"ok": true}') }, { label: "Three", content: disclosure("More details", h("p", {}, "Hidden until opened.")) }])),
      ),
    ),
    section(
      "Table",
      table(SAMPLE_ROWS, [
        { key: "name", label: "Building" },
        { key: "floors", label: "Floors", num: true },
        { key: "savings_usd", label: "Savings / yr", num: true, format: (v) => fmt.money(v) },
        { key: "confidence", label: "Confidence", num: true, format: (v) => fmt.pct(v, 0) },
      ]),
    ),
    section("Map (MapLibre, SVG fallback offline)", mapEl),
    section("Chart (Chart.js, SVG fallback offline)", chartEl),
    section(
      "States and overlays",
      h("div", { class: "grid cols-3" }, card({ title: "Loading" }, skeleton(4), h("div", { class: "row", style: { marginTop: "12px" } }, spinner(), h("span", { class: "faint" }, "Working…"))), emptyState("Nothing here yet."), errorState(new Error("Network error: the server did not answer."))),
      h("div", { class: "row", style: { marginTop: "16px" } }, button("Show toast", { onClick: () => toast("Saved.") }), button("Warning toast", { onClick: () => toast("Check this.", "warn") }), button("Open drawer", { onClick: () => drawer("Drawer", h("p", {}, "Settings or details go here.")) })),
      h("div", { style: { marginTop: "16px" } }, dropzone({ onFiles: (files) => toast(`${files.length} file(s) picked`) })),
    ),
  );
  // Map and chart load independently: a slow basemap must not hold up the chart.
  queueMicrotask(() => {
    createMap(mapEl, {
      geojson: SAMPLE_GEOJSON,
      zoom: 15.4,
      pitch: 50,
      extrude: { height: "height_m" },
      color: (p) => (p.value > 200 ? cssVar("--hot") : cssVar("--accent")),
      tooltip: (p) => [[p.name], ["Value", fmt.number(p.value)]],
      onClick: (p) => toast(`Clicked ${p.name}`),
    });
    createChart(chartEl, {
      type: "bar",
      labels: SAMPLE_ROWS.map((r) => r.name),
      series: [{ label: "Savings / yr", data: SAMPLE_ROWS.map((r) => r.savings_usd) }],
      format: (v) => fmt.compact(v),
    });
  });
  return page;
}
