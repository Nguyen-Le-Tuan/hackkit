// Boot: config -> theme -> live/static mode -> nav -> router. Pages live in js/pages/.

import * as api from "./api.js";
import * as prefs from "./prefs.js";
import { resolve } from "./route.js";
import { h, mount, icon, chip, button, drawer, errorState, linkButton, toast, skeleton } from "./ui.js";
import * as home from "./pages/home.js";
import * as feature from "./pages/feature.js";
import * as kit from "./pages/kit.js";
import * as doctor from "./pages/doctor.js";
import { pages as customPages } from "./pages/index.js";

const DEFAULT_CONFIG = {
  name: "hackkit",
  tagline: "",
  accent: "",
  logo: "assets/logo.svg",
  hero: {},
  steps: [],
  impact: [],
  links: {},
  footer: "",
  nav_features: true,
};

async function loadConfig() {
  try {
    const response = await fetch("config.json", { cache: "no-cache" });
    return { ...DEFAULT_CONFIG, ...(await response.json()) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  prefs.set("theme", theme);
}

function modeChip() {
  const mode = api.mode();
  const info = api.health() || {};
  if (mode === "live") {
    const demo = prefs.get("demo_mode") ?? info.demo_mode;
    const provider = prefs.get("provider") || info.provider;
    return chip(`Live · ${provider}${demo ? " · demo mode" : ""}`, demo ? "warn" : "");
  }
  if (mode === "static") return chip("Static demo", "info");
  return chip("No server", "bad");
}

function settingsDrawer(refresh) {
  const info = api.health() || {};
  const live = api.mode() === "live";
  const provider = h(
    "select",
    { class: "select", disabled: !live, onchange: (e) => (prefs.set("provider", e.target.value || null), refresh()) },
    h("option", { value: "" }, `Server default (${info.provider || "?"})`),
    (info.providers || []).map((p) => h("option", { value: p, selected: prefs.get("provider") === p }, p)),
  );
  const demo = h("input", {
    type: "checkbox",
    checked: Boolean(prefs.get("demo_mode") ?? info.demo_mode),
    disabled: !live,
    onchange: (e) => (prefs.set("demo_mode", e.target.checked), refresh()),
  });
  drawer(
    "Settings",
    h("label", { class: "field" }, h("span", { class: "label" }, "Model provider"), provider, h("span", { class: "hint" }, "fake = no key, no network: use it to rehearse.")),
    h("label", { class: "switch" }, demo, h("span", {}, "Demo mode: replay saved results only")),
    button("Clear saved model results", {
      kind: "danger",
      disabled: !live,
      onClick: async () => {
        try {
          const { removed } = await api.clearCache();
          toast(`Cleared ${removed} saved result(s).`);
        } catch (error) {
          toast(error.message, "bad");
        }
      },
    }),
    h(
      "p",
      { class: "faint" },
      live ? "Overrides apply to this browser only." : "Static demo: settings need the live server (make run).",
    ),
    h("div", { class: "row" }, linkButton("Doctor", "#/doctor", { size: "sm", iconName: "pulse" }), linkButton("UI kit", "#/kit", { size: "sm", iconName: "grid" }), live ? linkButton("API docs", "api/docs", { size: "sm", iconName: "link", external: true }) : null),
  );
}

async function boot() {
  const config = await loadConfig();
  if (config.accent) document.documentElement.style.setProperty("--accent", config.accent);
  applyTheme(prefs.get("theme") || config.theme || "dark");
  document.title = config.name;

  const forceStatic = new URLSearchParams(location.search).has("static");
  await api.init({ forceStatic });
  let features = [];
  try {
    features = await api.features();
  } catch {
    features = [];
  }

  const routes = [
    { path: "/", title: "Home", icon: "home", nav: true, render: home.render },
    ...customPages,
    ...(config.nav_features ? features.map((f) => ({ path: `/feature/${f.key}`, title: f.title, icon: "spark", nav: true, render: feature.render, params: { key: f.key } })) : []),
    { path: "/feature/:key", title: "Feature", nav: false, render: feature.render },
    { path: "/kit", title: "UI kit", nav: false, render: kit.render },
    { path: "/doctor", title: "Doctor", nav: false, render: doctor.render },
  ];

  const nav = h("nav", { class: "nav", "aria-label": "Main" }, routes.filter((r) => r.nav).map((r) => h("a", { href: `#${r.path}`, dataset: { path: r.path } }, icon(r.icon || "spark"), h("span", {}, r.title))));
  const tools = h("div", { class: "tools" });
  const refreshTools = () =>
    mount(
      tools,
      modeChip(),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Toggle theme", title: "Toggle light/dark", onclick: () => (applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"), refreshTools(), render()) }, icon(document.documentElement.dataset.theme === "light" ? "moon" : "sun")),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Settings", title: "Settings", onclick: () => settingsDrawer(refreshTools) }, icon("settings")),
    );
  refreshTools();

  const logo = config.logo ? h("img", { src: config.logo, alt: "" }) : null;
  const header = h("header", { class: "topbar" }, h("a", { class: "brand", href: "#/" }, logo, h("span", { class: "name" }, config.name)), nav, tools);
  const main = h("main", { class: "app-main", id: "main" });
  const links = config.links || {};
  const footer = h(
    "footer",
    { class: "footer" },
    h("span", {}, config.footer || `${config.name}${config.tagline ? ` · ${config.tagline}` : ""}`),
    h(
      "span",
      { class: "row" },
      links.repo ? h("a", { href: links.repo, target: "_blank", rel: "noopener" }, "Code") : null,
      links.devpost ? h("a", { href: links.devpost, target: "_blank", rel: "noopener" }, "Devpost") : null,
      links.video ? h("a", { href: links.video, target: "_blank", rel: "noopener" }, "Video") : null,
      h("a", { href: "#/doctor" }, "Doctor"),
      h("a", { href: "#/kit" }, "UI kit"),
    ),
  );
  mount(document.getElementById("app"), header, main, footer);

  let renderId = 0;
  async function render() {
    const id = ++renderId;
    const found = resolve(routes, location.hash);
    for (const a of nav.querySelectorAll("a")) a.classList.toggle("active", found?.route.path === a.dataset.path);
    if (!found) {
      mount(main, h("div", { class: "page" }, errorState(new Error(`No page at ${location.hash}`), linkButton("Go home", "#/", { kind: "primary" }))));
      return;
    }
    const { route } = found;
    const params = { ...found.params, ...(route.params || {}) };
    document.title = route.path === "/" ? config.name : `${route.title === "Feature" ? params.key : route.title} · ${config.name}`;
    mount(main, h("div", { class: "page" }, skeleton(6)));
    try {
      const node = await route.render({ params, query: found.query, config });
      if (id !== renderId) return; // a newer navigation won
      mount(main, node);
      window.scrollTo({ top: 0 });
    } catch (error) {
      console.error(error);
      if (id === renderId) mount(main, h("div", { class: "page" }, errorState(error, linkButton("Go home", "#/", { kind: "primary" }))));
    }
  }
  window.addEventListener("hashchange", render);
  await render();
  document.documentElement.dataset.ready = "true"; // screenshot/video scripts wait for this
}

boot().catch((error) => {
  console.error(error);
  mount(document.getElementById("app"), h("div", { class: "page" }, errorState(error)));
});
