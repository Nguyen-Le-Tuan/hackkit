// Chart helper: Chart.js from a CDN, themed with the app's CSS variables, with a built-in SVG
// bar-chart fallback when offline.
//
//   await createChart(el, {
//     type: "bar",                       // "bar" | "line" | "doughnut"
//     labels: ["Jan", "Feb"],
//     series: [{ label: "Savings", data: [120, 340] }, { label: "Demo", data: [90, 80], demo: true }],
//     format: (v) => fmt.money(v),       // axis + tooltip formatting
//   });

import { loadScript } from "./lazy.js";
import { h } from "./ui.js";

const CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js";

function cssVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function palette() {
  return [cssVar("--accent", "#2dd4bf"), cssVar("--hot", "#f59e0b"), cssVar("--info", "#60a5fa"), cssVar("--good", "#34d399"), "#a78bfa", "#f472b6"];
}

export async function createChart(el, options) {
  el.classList.add("chart");
  try {
    const Chart = await loadScript(CHARTJS, "Chart");
    return chartJs(Chart, el, options);
  } catch (error) {
    console.info("Chart fallback to SVG:", error.message);
    return svgBars(el, options);
  }
}

function chartJs(Chart, el, { type = "bar", labels, series, format = (v) => String(v) }) {
  const colors = palette();
  const demo = cssVar("--demo", "#ef4444");
  const text = cssVar("--muted", "#92a9b0");
  const grid = cssVar("--border", "#1f363f");
  const canvas = h("canvas", { role: "img", "aria-label": series.map((s) => s.label).join(", ") });
  el.replaceChildren(canvas);
  const chart = new Chart(canvas, {
    type,
    data: {
      labels,
      datasets: series.map((s, i) => {
        const color = s.demo ? demo : s.color || colors[i % colors.length];
        return {
          label: s.label,
          data: s.data,
          backgroundColor: type === "doughnut" ? colors : color,
          borderColor: color,
          borderWidth: type === "line" ? 2 : 0,
          borderRadius: type === "bar" ? 6 : 0,
          tension: 0.3,
        };
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { labels: { color: text }, display: series.length > 1 || type === "doughnut" },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${format(ctx.parsed.y ?? ctx.parsed)}` } },
      },
      scales:
        type === "doughnut"
          ? {}
          : {
              x: { ticks: { color: text }, grid: { color: grid } },
              y: { ticks: { color: text, callback: (v) => format(v) }, grid: { color: grid }, beginAtZero: true },
            },
    },
  });
  return { kind: "chartjs", chart };
}

function svgBars(el, { labels, series, format = (v) => String(v) }) {
  const ns = "http://www.w3.org/2000/svg";
  const W = 800;
  const H = 300;
  const values = series[0]?.data || [];
  const max = Math.max(...values, 1);
  const bw = (W - 40) / Math.max(values.length, 1);
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.style.width = "100%";
  svg.style.height = "100%";
  const color = series[0]?.demo ? cssVar("--demo", "#ef4444") : cssVar("--accent", "#2dd4bf");
  values.forEach((v, i) => {
    const bh = ((H - 50) * v) / max;
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("x", 20 + i * bw + bw * 0.15);
    rect.setAttribute("y", H - 30 - bh);
    rect.setAttribute("width", bw * 0.7);
    rect.setAttribute("height", bh);
    rect.setAttribute("rx", 5);
    rect.setAttribute("fill", color);
    const title = document.createElementNS(ns, "title");
    title.textContent = `${labels[i]}: ${format(v)}`;
    rect.append(title);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", 20 + i * bw + bw / 2);
    label.setAttribute("y", H - 10);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("font-size", "12");
    label.setAttribute("fill", cssVar("--muted", "#92a9b0"));
    label.textContent = labels[i];
    svg.append(rect, label);
  });
  el.replaceChildren(svg);
  return { kind: "svg", chart: null };
}
