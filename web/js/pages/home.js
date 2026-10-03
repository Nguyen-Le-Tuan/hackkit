// Home page: what the product does in 10 seconds, the impact number, and where to click.
// Everything comes from web/config.json, so a team edits words, not code.

import * as api from "../api.js";
import { h, icon, linkButton, badge, card, metricTile, metrics, emptyState, codeBlock } from "../ui.js";

function heroTitle(title, highlight) {
  if (!highlight || !title.includes(highlight)) return h("h1", {}, title);
  const [before, after] = title.split(highlight, 2);
  return h("h1", {}, before, h("em", {}, highlight), after);
}

export async function render({ config }) {
  const hero = config.hero || {};
  const features = await api.features();
  const first = features[0];
  const cta = hero.cta || (first ? { label: `Try ${first.title}`, href: `#/feature/${first.key}` } : null);

  const page = h("div", { class: "page fade-in" });
  const heroText = h(
      "div",
      { class: "hero-text" },
      hero.eyebrow ? h("div", { class: "eyebrow" }, hero.eyebrow) : null,
      heroTitle(hero.title || config.name, hero.highlight),
      hero.lede ? h("p", { class: "lede" }, hero.lede) : null,
      h(
        "div",
        { class: "actions" },
        cta ? linkButton(cta.label, cta.href, { kind: "primary", size: "lg", iconName: "play" }) : null,
        config.links?.video ? linkButton("Watch the 2-minute demo", config.links.video, { size: "lg", iconName: "play", external: true }) : null,
        h("a", { class: "btn lg ghost", href: "#how" }, "How it works"),
      ),
      hero.proof?.length ? h("div", { class: "proof" }, hero.proof.map((text) => badge(text, "accent"))) : null,
  );
  // Optional product shot on the right: put a `make shots` screenshot in web/assets/ and set hero.image.
  const heroImage = hero.image ? h("img", { class: "hero-shot", src: hero.image, alt: hero.image_alt || `${config.name} screenshot` }) : null;
  page.append(h("section", { class: ["hero", heroImage && "with-image"] }, heroText, heroImage));

  if (config.impact?.length) {
    page.append(
      h(
        "section",
        { class: "section" },
        h("div", { class: "section-head" }, h("h2", {}, config.impact_title || "Impact"), config.impact_note ? h("span", { class: "faint" }, config.impact_note) : null),
        metrics(config.impact.map((m) => metricTile(m.label, m.value, { foot: m.note ? h("span", {}, m.note) : null, demo: Boolean(m.demo), big: true }))),
      ),
    );
  }

  page.append(
    h(
      "section",
      { class: "section" },
      h("div", { class: "section-head" }, h("h2", {}, "Try it"), h("span", { class: "faint" }, `${features.length} feature${features.length === 1 ? "" : "s"}`)),
      features.length
        ? h(
            "div",
            { class: "grid auto" },
            features.map((f) =>
              card(
                { hover: true },
                h("div", { class: "stack tight" }, h("div", { class: "row" }, icon("spark", 20), h("h3", {}, f.title)), h("p", { class: "muted" }, f.description), f.tags?.length ? h("div", { class: "row" }, f.tags.map((t) => badge(t))) : null),
                h("div", { class: "card-foot" }, linkButton("Open", `#/feature/${f.key}`, { kind: "primary", size: "sm", iconName: "arrow" })),
              ),
            ),
          )
        : emptyState("No features yet. Create one with:", codeBlock('make feature NAME=my_feature TITLE="My feature"')),
    ),
  );

  if (config.steps?.length) {
    page.append(
      h(
        "section",
        { class: "section", id: "how" },
        h("h2", {}, "How it works"),
        h("div", { class: "steps" }, config.steps.map((s) => h("div", { class: "step" }, h("h4", {}, s.title), h("p", {}, s.text)))),
      ),
    );
  }
  return page;
}
