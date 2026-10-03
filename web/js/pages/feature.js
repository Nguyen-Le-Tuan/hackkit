// Generic feature runner: works for every registered feature with no code.
// Input (text + files) -> POST /api/run/<key> -> summary, metrics, review flags, data, downloads.
// Build a custom page in web/js/pages/ when a feature deserves a bespoke demo (map, chart...).

import * as api from "../api.js";
import * as fmt from "../fmt.js";
import {
  h, mount, icon, button, badge, card, metricTile, metrics, callout, dataView, codeBlock,
  disclosure, skeleton, errorState, emptyState, dropzone, fileToBase64, download, copyText, tabs,
} from "../ui.js";

const ACCEPT = { image: "image/png,image/jpeg,image/webp", pdf: "application/pdf" };

export async function render({ params }) {
  const feature = await api.feature(params.key);
  const files = [];
  const textarea = h("textarea", { class: "textarea", id: "input-text", "aria-label": "Input text", spellcheck: "false" });
  textarea.value = feature.sample_text || "";
  const fileList = h("div", { class: "files" });
  const result = h("div", { "aria-live": "polite" });
  const runBtn = button("Run", { kind: "primary", size: "lg", iconName: "play", onClick: () => run() });
  runBtn.id = "run";

  const accepts = feature.accepts.filter((kind) => ACCEPT[kind]);
  const showFiles = () =>
    mount(
      fileList,
      files.map((f, i) =>
        h("span", { class: "chip" }, icon("file", 14), `${f.name} (${fmt.number(f.size / 1024, 0)} KB)`, h("button", { class: "btn ghost sm", type: "button", "aria-label": `Remove ${f.name}`, onclick: () => (files.splice(i, 1), showFiles()) }, "×")),
      ),
    );

  const examples = [feature.sample_text, ...(feature.demo_inputs || [])].filter(Boolean);
  const inputCard = card(
    {
      title: "Input",
      actions: examples.length > 1
        ? h("div", { class: "row" }, examples.map((text, i) => button(`Example ${i + 1}`, { size: "sm", kind: "ghost", onClick: () => (textarea.value = text) })))
        : examples.length
          ? button("Reset sample", { size: "sm", kind: "ghost", onClick: () => (textarea.value = examples[0]) })
          : null,
    },
    h(
      "div",
      { class: "stack" },
      textarea,
      accepts.length
        ? dropzone({
            accept: accepts.map((k) => ACCEPT[k]).join(","),
            label: `Or drop ${accepts.join(" / ")} files here`,
            onFiles: (picked) => {
              files.push(...picked);
              showFiles();
            },
          })
        : null,
      fileList,
      h("div", { class: "row between" }, h("span", { class: "faint" }, h("kbd", {}, "Ctrl"), " + ", h("kbd", {}, "Enter"), " to run"), runBtn),
    ),
  );
  textarea.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") run();
  });

  mount(result, card({ title: "Result" }, emptyState("Run the feature to see what the model read and what the code checked.")));

  async function run() {
    runBtn.disabled = true;
    const started = performance.now();
    mount(result, card({ title: "Result" }, skeleton(5)));
    try {
      const attachments = await Promise.all(files.map(async (f) => ({ name: f.name, media_type: f.type || "application/octet-stream", data_b64: await fileToBase64(f) })));
      const payload = await api.run(feature.key, { text: textarea.value, attachments });
      mount(result, renderResult(feature, payload, performance.now() - started));
    } catch (error) {
      mount(result, card({ title: "Result" }, errorState(error, button("Try again", { onClick: () => run() }))));
    } finally {
      runBtn.disabled = false;
    }
  }

  return h(
    "div",
    { class: "page fade-in" },
    h(
      "header",
      { class: "page-head" },
      h("div", {}, h("div", { class: "eyebrow" }, "Feature"), h("h1", {}, feature.title), h("p", { class: "lede" }, feature.description)),
      feature.tags?.length ? h("div", { class: "row" }, feature.tags.map((t) => badge(t))) : null,
    ),
    h("div", { class: "grid split" }, inputCard, result),
  );
}

function provenance(payload, ms) {
  if (payload.static) {
    return payload.static_input_matched
      ? badge("Saved demo result", "info")
      : badge("Static demo: showing the saved example", "warn");
  }
  if (payload.from_cache) return badge(`Saved result · ${fmt.duration(ms)}`, "info");
  return badge(`${fmt.plural(payload.attempts, "model call")} · ${fmt.duration(ms)}`, "accent");
}

export function renderResult(feature, payload, ms = 0) {
  if (!payload.ok) {
    return card(
      { title: "Result", actions: provenance(payload, ms) },
      h(
        "div",
        { class: "stack" },
        callout("bad", "Could not read this input.", payload.error || ""),
        payload.raw_text ? disclosure("Model output", codeBlock(payload.raw_text)) : null,
      ),
    );
  }
  const metricEntries = Object.entries(payload.metrics || {});
  const data = { ...(payload.data || {}) };
  const confidence = data.confidence;
  delete data.confidence;
  delete data.uncertain_fields;

  return card(
    { title: "Result", actions: provenance(payload, ms) },
    h(
      "div",
      { class: "stack loose fade-in" },
      payload.summary ? h("h3", {}, payload.summary) : null,
      metricEntries.length ? metrics(metricEntries.map(([key, value]) => metricTile(fmt.humanize(key), fmt.metric(key, value), { foot: h("span", {}, "computed by code") }))) : null,
      payload.flags.length
        ? h("div", { class: "stack tight" }, h("h4", {}, "Needs human review"), payload.flags.map((f) => callout("warn", f.field === "*" ? "Overall" : fmt.humanize(f.field), f.reason)))
        : callout("good", "Nothing flagged.", "The code checks passed."),
      tabs([
        { label: "Data", render: () => h("div", { class: "stack" }, fmt.isNumber(confidence) ? h("p", { class: "faint" }, `Model confidence: ${fmt.pct(confidence, 0)}`) : null, dataView(data)) },
        { label: "JSON", render: () => codeBlock(JSON.stringify(payload.data, null, 2)) },
        { label: "Report", render: () => codeBlock(payload.markdown) },
      ]),
      h(
        "div",
        { class: "row" },
        button("Download report (.md)", { size: "sm", iconName: "download", onClick: () => download(`${feature.key}-report.md`, payload.markdown, "text/markdown") }),
        button("Download data (.json)", { size: "sm", iconName: "download", onClick: () => download(`${feature.key}.json`, payload.json, "application/json") }),
        button("Copy JSON", { size: "sm", kind: "ghost", iconName: "copy", onClick: () => copyText(payload.json) }),
      ),
    ),
  );
}

