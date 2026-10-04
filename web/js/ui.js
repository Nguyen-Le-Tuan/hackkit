// UI kit in plain JS. h() builds DOM nodes safely: strings become text, never HTML, so data from
// the API or a model can never inject markup. Components return nodes; see them all on #/kit.

import * as fmt from "./fmt.js";

/* ---------------------------------------------------------------- DOM helper */

/**
 * h("div", {class: "card", onclick: fn}, "text", child, [more, children])
 * Attributes: class, style (string or object), dataset (object), on<event> (function),
 * any other attribute as a string; boolean true -> present, false/null -> absent.
 */
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === false || value === null || value === undefined) continue;
    if (name === "class") node.className = Array.isArray(value) ? value.filter(Boolean).join(" ") : value;
    else if (name === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (name === "dataset") Object.assign(node.dataset, value);
    else if (name.startsWith("on") && typeof value === "function") node.addEventListener(name.slice(2), value);
    else if (name === "value" && "value" in node) node.value = value;
    else node.setAttribute(name, value === true ? "" : String(value));
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function mount(node, ...children) {
  clear(node);
  append(node, children);
  return node;
}

/* ---------------------------------------------------------------- icons */

const ICONS = {
  home: '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  play: '<path d="M7 4l13 8-13 8z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  map: '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  file: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>',
  upload: '<path d="M12 16V4M6 10l6-6 6 6"/><path d="M4 20h16"/>',
  download: '<path d="M12 4v12M6 10l6 6 6-6"/><path d="M4 20h16"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  check: '<path d="M4 12l5 5L20 6"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v4M12 18h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
};

export function icon(name, size = null) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", size || 18); // CSS (e.g. .btn svg) may override
  svg.setAttribute("height", size || 18);
  svg.innerHTML = ICONS[name] || ICONS.spark; // trusted constant markup only
  return svg;
}
export const iconNames = Object.keys(ICONS);

/* ---------------------------------------------------------------- basics */

export function button(label, { kind = "", size = "", iconName = null, onClick, disabled = false, type = "button", title } = {}) {
  return h(
    "button",
    { class: ["btn", kind, size], type, disabled, title, onclick: onClick },
    iconName ? icon(iconName) : null,
    label,
  );
}

export function linkButton(label, href, { kind = "", size = "", iconName = null, external = false } = {}) {
  return h(
    "a",
    { class: ["btn", kind, size], href, target: external ? "_blank" : null, rel: external ? "noopener" : null },
    iconName ? icon(iconName) : null,
    label,
  );
}

export function badge(text, kind = "") {
  return h("span", { class: ["badge", kind] }, text);
}

export function chip(text, kind = "") {
  return h("span", { class: ["chip", kind] }, h("span", { class: "dot" }), text);
}

/** Where a number came from: source("OpenStreetMap", 0.9) */
export function source(name, confidence = null, note = "") {
  return h(
    "span",
    { class: "source", title: note || null },
    name,
    fmt.isNumber(confidence) ? h("span", { class: "conf" }, confidence.toFixed(2)) : null,
  );
}

/** Red label for made-up / illustrative values. Use with class "demo-value" on the number. */
export function demoBadge(text = "DEMO value") {
  return h("span", { class: "badge demo", title: "Illustrative value, not real data" }, text);
}

export function card({ title = null, actions = null, flush = false, hover = false, className = "" } = {}, ...body) {
  const head = title || actions ? h("div", { class: "card-head" }, title ? h("h3", {}, title) : h("span"), actions) : null;
  return h("section", { class: ["card", flush && "flush", hover && "hover", className] }, head, flush ? h("div", { class: "card-body" }, body) : body);
}

/** metricTile("Total", "$1,234", {foot: source(...), demo: true}) */
export function metricTile(label, value, { foot = null, demo = false, warn = false, big = false } = {}) {
  return h(
    "div",
    { class: ["metric", demo && "demo", warn && "warn", big && "big"] },
    h("div", { class: "label" }, label),
    h("div", { class: "value" }, value),
    foot || demo ? h("div", { class: "foot" }, demo ? demoBadge() : null, foot) : null,
  );
}

export function metrics(entries) {
  return h("div", { class: "metrics" }, entries);
}

export function callout(kind, title, text = "") {
  const iconFor = { good: "check", warn: "alert", bad: "alert", info: "info", demo: "alert" }[kind] || "info";
  return h("div", { class: ["callout", kind], role: kind === "bad" ? "alert" : null }, icon(iconFor), h("div", {}, title ? h("b", {}, title, " ") : null, text));
}

export function kv(entries) {
  const dl = h("dl", { class: "kv" });
  for (const [key, value] of entries) dl.append(h("dt", {}, key), h("dd", {}, value instanceof Node ? value : fmt.display(value)));
  return dl;
}

/**
 * table(rows, columns) — rows: objects; columns: [{key, label, num, format(value,row) -> text|Node}]
 * Without columns, uses the keys of the first rows.
 */
export function table(rows, columns = null, { empty = "Nothing to show." } = {}) {
  if (!rows || !rows.length) return emptyState(empty);
  const cols =
    columns ||
    [...new Set(rows.slice(0, 20).flatMap((row) => Object.keys(row)))].slice(0, 10).map((key) => ({
      key,
      label: fmt.humanize(key),
      num: rows.every((row) => row[key] == null || fmt.isNumber(row[key])),
    }));
  const head = h("tr", {}, cols.map((c) => h("th", { class: c.num ? "num" : null }, c.label ?? fmt.humanize(c.key))));
  const body = rows.map((row) =>
    h(
      "tr",
      {},
      cols.map((c) => {
        const raw = row[c.key];
        const shown = c.format ? c.format(raw, row) : fmt.display(raw);
        return h("td", { class: c.num ? "num" : null }, shown);
      }),
    ),
  );
  return h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, head), h("tbody", {}, body)));
}

export function tabs(items, { selected = 0, onChange } = {}) {
  const panel = h("div", { class: "tab-panel" });
  const bar = h("div", { class: "tabs", role: "tablist" });
  const show = (index) => {
    [...bar.children].forEach((b, i) => b.setAttribute("aria-selected", String(i === index)));
    mount(panel, typeof items[index].render === "function" ? items[index].render() : items[index].content);
    onChange?.(index);
  };
  items.forEach((item, i) => bar.append(h("button", { role: "tab", type: "button", onclick: () => show(i) }, item.label)));
  show(selected);
  return h("div", {}, bar, panel);
}

export function codeBlock(text) {
  return h("pre", { class: "code" }, h("code", {}, text));
}

export function disclosure(summary, ...body) {
  return h("details", { class: "disclosure" }, h("summary", {}, summary), body);
}

/**
 * Plain-English question box for hackkit.ask: the model turns the question into a filter,
 * your route runs it. onAsk(question) -> Promise<{understood: string, node: Node}>.
 * Showing "Understood as: ..." makes the AI visible AND auditable on stage.
 */
export function askBox({ placeholder = "Ask in plain English…", examples = [], onAsk }) {
  const input = h("input", { class: "input lg", type: "search", placeholder, "aria-label": "Question" });
  const out = h("div", { class: "stack tight", "aria-live": "polite" });
  const go = async (question = input.value) => {
    if (!question.trim()) return;
    input.value = question;
    mount(out, skeleton(3));
    try {
      const { understood, node } = await onAsk(question);
      mount(out, h("p", { class: "faint" }, icon("spark", 14), " Understood as: ", h("b", {}, understood)), node);
    } catch (error) {
      mount(out, errorState(error));
    }
  };
  input.addEventListener("keydown", (event) => event.key === "Enter" && go());
  return h(
    "div",
    { class: "stack" },
    h("div", { class: "row", style: { flexWrap: "nowrap" } }, input, button("Ask", { kind: "primary", size: "lg", iconName: "search", onClick: () => go() })),
    examples.length ? h("div", { class: "row" }, h("span", { class: "faint" }, "Try:"), examples.map((q) => h("button", { class: "chip", type: "button", onclick: () => go(q) }, q))) : null,
    out,
  );
}

/* ---------------------------------------------------------------- states */

export function skeleton(lines = 3) {
  return h(
    "div",
    { class: "stack tight", "aria-busy": "true", "aria-label": "Loading" },
    Array.from({ length: lines }, (_, i) => h("div", { class: "skeleton", style: { width: `${92 - i * 14}%`, height: i === 0 ? "26px" : "14px" } })),
  );
}

export function spinner() {
  return h("span", { class: "spinner", role: "status", "aria-label": "Loading" });
}

export function emptyState(text = "Nothing here yet.", action = null) {
  return h("div", { class: "empty" }, icon("inbox"), h("p", {}, text), action);
}

export function errorState(error, action = null) {
  const message = error?.message || String(error);
  return h("div", { class: "error-state", role: "alert" }, icon("alert"), h("p", {}, message), action);
}

/* ---------------------------------------------------------------- overlays */

let toastBox = null;
export function toast(message, kind = "good", ms = 3200) {
  if (!toastBox) toastBox = document.body.appendChild(h("div", { class: "toasts", "aria-live": "polite" }));
  const node = h("div", { class: ["toast", kind] }, message);
  toastBox.append(node);
  setTimeout(() => node.remove(), ms);
}

export function drawer(title, ...body) {
  const close = () => {
    overlay.remove();
    panel.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (event) => event.key === "Escape" && close();
  const overlay = h("div", { class: "overlay", onclick: close });
  const panel = h(
    "aside",
    { class: "drawer", role: "dialog", "aria-label": title },
    h("div", { class: "row between" }, h("h3", {}, title), h("button", { class: "icon-btn", type: "button", "aria-label": "Close", onclick: close }, icon("x"))),
    h("div", { class: "stack", style: { marginTop: "20px" } }, body),
  );
  document.addEventListener("keydown", onKey);
  document.body.append(overlay, panel);
  return close;
}

/* ---------------------------------------------------------------- files */

export function download(filename, text, mime = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }));
  const a = h("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch {
    toast("Copy failed: select the text and copy it by hand", "warn");
  }
}

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Drag-and-drop + click file picker. onFiles receives File[]. */
export function dropzone({ accept = "", multiple = true, label = "Drop files here or click to choose", onFiles }) {
  const input = h("input", { type: "file", accept, multiple, hidden: true, onchange: () => onFiles([...input.files]) });
  const zone = h(
    "label",
    { class: "dropzone", tabindex: "0" },
    icon("upload"),
    h("span", {}, label),
    input,
  );
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("over");
    onFiles([...event.dataTransfer.files]);
  });
  zone.addEventListener("keydown", (event) => (event.key === "Enter" || event.key === " ") && input.click());
  return zone;
}

/** True for hackkit.provenance.Sourced JSON: {"value": ..., "source": {"source": ...}}. */
export function isSourced(value) {
  return Boolean(value && typeof value === "object" && "value" in value && value.source && typeof value.source.source === "string");
}

/** A value with its source badge; DEMO sources are red. format(value) -> text. */
export function sourcedView(item, format = fmt.display) {
  const prov = item.source;
  const demo = prov.source.trim().toLowerCase() === "demo";
  return h(
    "span",
    { class: "row", style: { gap: "8px", display: "inline-flex" } },
    h("span", { class: demo ? "demo-value" : null }, format(item.value)),
    demo ? demoBadge() : source(prov.source, prov.confidence ?? null, prov.note || ""),
  );
}

/** Render any JSON value as readable UI: scalars -> kv, lists of objects -> table. */
export function dataView(value, depth = 0) {
  if (value === null || value === undefined) return h("span", { class: "faint" }, "—");
  if (isSourced(value)) return sourcedView(value);
  if (Array.isArray(value)) {
    if (!value.length) return h("span", { class: "faint" }, "None");
    if (value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
      const keys = [...new Set(value.slice(0, 20).flatMap((item) => Object.keys(item)))].slice(0, 10);
      const columns = keys.map((key) => ({
        key,
        label: fmt.humanize(key),
        num: value.every((row) => row[key] == null || fmt.isNumber(row[key]) || (isSourced(row[key]) && fmt.isNumber(row[key].value))),
        format: (v) => (isSourced(v) ? sourcedView(v) : v && typeof v === "object" ? JSON.stringify(v) : fmt.display(v)),
      }));
      return table(value, columns);
    }
    return h("span", {}, value.map(fmt.display).join(", "));
  }
  if (typeof value === "object") {
    if (depth > 2) return codeBlock(JSON.stringify(value, null, 2));
    return kv(Object.entries(value).map(([key, inner]) => [fmt.humanize(key), inner && typeof inner === "object" ? dataView(inner, depth + 1) : fmt.display(inner)]));
  }
  return h("span", {}, fmt.display(value));
}
