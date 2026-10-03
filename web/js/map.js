// Map helper: MapLibre GL from a CDN (2D/3D, hover tooltips, click), and a plain SVG fallback
// when the CDN or the basemap is unreachable, so the demo never shows an empty box.
//
//   const map = await createMap(el, {
//     geojson,                         // FeatureCollection of Points and/or Polygons
//     center: [-78.88, 42.89], zoom: 14, pitch: 50,
//     basemap: "auto",                 // "dark" | "light" | "blank" | "auto" (follows theme)
//     extrude: { height: "height_m" }, // optional: 3D polygons using a property in metres
//     color: (props) => "#2dd4bf",     // optional: per-feature colour
//     tooltip: (props) => [["Name", props.name], ["Savings", "$1,200"]],  // rows; text only
//     onClick: (props) => {},
//   });
//   map.kind -> "maplibre" | "svg"

import { loadCss, loadScript } from "./lazy.js";
import { h } from "./ui.js";

const MAPLIBRE = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl";
const BASEMAPS = {
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
};
export const ATTRIBUTION = "© OpenStreetMap contributors © CARTO";

function cssVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function blankStyle() {
  return { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": cssVar("--bg-2", "#0a161a") } }] };
}

function tooltipNode(rows) {
  if (!rows) return null;
  if (typeof rows === "string") return h("div", {}, rows);
  return h(
    "div",
    { class: "stack tight", style: { gap: "2px" } },
    rows.map(([key, value], i) => (i === 0 && value === undefined ? h("b", {}, key) : h("div", {}, h("span", { class: "faint" }, `${key}: `), value instanceof Node ? value : String(value ?? "—")))),
  );
}

function withColors(geojson, color) {
  const accent = cssVar("--accent", "#2dd4bf");
  return {
    ...geojson,
    features: geojson.features.map((f, i) => ({ ...f, id: i, properties: { ...f.properties, __color: color ? color(f.properties || {}) : accent } })),
  };
}

export async function createMap(el, options) {
  const opts = { basemap: "auto", zoom: 13, pitch: 0, bearing: 0, ...options };
  el.classList.add("map");
  const theme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const basemap = opts.basemap === "auto" ? theme : opts.basemap;
  try {
    loadCss(`${MAPLIBRE}.css`);
    const maplibregl = await loadScript(`${MAPLIBRE}.js`, "maplibregl");
    return await maplibreMap(maplibregl, el, opts, basemap);
  } catch (error) {
    console.info("Map fallback to SVG:", error.message);
    return svgMap(el, opts);
  }
}

async function maplibreMap(maplibregl, el, opts, basemap) {
  const style = basemap === "blank" || !navigator.onLine ? blankStyle() : BASEMAPS[basemap] || BASEMAPS.dark;
  const map = new maplibregl.Map({
    container: el,
    style,
    center: opts.center || centerOf(opts.geojson),
    zoom: opts.zoom,
    pitch: opts.pitch,
    bearing: opts.bearing,
    // CARTO styles carry their own attribution; the blank style needs ours.
    attributionControl: typeof style === "string" ? { compact: true } : { compact: true, customAttribution: ATTRIBUTION },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("basemap timeout")), 8000);
    map.once("load", () => {
      clearTimeout(timer);
      resolve();
    });
    map.once("error", (event) => {
      if (!map.loaded()) {
        clearTimeout(timer);
        map.setStyle(blankStyle());
        map.once("styledata", resolve);
      } else console.warn(event.error);
    });
  });
  const data = withColors(opts.geojson, opts.color);
  map.addSource("data", { type: "geojson", data });
  const polygonFilter = ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false];
  if (opts.extrude) {
    map.addLayer({
      id: "polygons",
      type: "fill-extrusion",
      source: "data",
      filter: polygonFilter,
      paint: {
        "fill-extrusion-color": ["get", "__color"],
        "fill-extrusion-height": ["coalesce", ["get", opts.extrude.height], 10],
        "fill-extrusion-opacity": 0.85,
      },
    });
  } else {
    map.addLayer({ id: "polygons", type: "fill", source: "data", filter: polygonFilter, paint: { "fill-color": ["get", "__color"], "fill-opacity": 0.55 } });
  }
  map.addLayer({
    id: "points",
    type: "circle",
    source: "data",
    filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-color": ["get", "__color"], "circle-radius": 7, "circle-stroke-width": 2, "circle-stroke-color": cssVar("--bg", "#071013") },
  });
  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "300px", offset: 12 });
  for (const layer of ["polygons", "points"]) {
    map.on("mousemove", layer, (event) => {
      map.getCanvas().style.cursor = "pointer";
      const node = tooltipNode(opts.tooltip?.(event.features[0].properties));
      if (node) popup.setLngLat(event.lngLat).setDOMContent(node).addTo(map);
    });
    map.on("mouseleave", layer, () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });
    map.on("click", layer, (event) => opts.onClick?.(event.features[0].properties));
  }
  return { kind: "maplibre", map, setData: (geojson) => map.getSource("data").setData(withColors(geojson, opts.color)) };
}

function centerOf(geojson) {
  const coords = [];
  const walk = (c) => (typeof c[0] === "number" ? coords.push(c) : c.forEach(walk));
  geojson.features.forEach((f) => walk(f.geometry.coordinates));
  if (!coords.length) return [0, 0];
  const lon = coords.reduce((s, c) => s + c[0], 0) / coords.length;
  const lat = coords.reduce((s, c) => s + c[1], 0) / coords.length;
  return [lon, lat];
}

/** Offline fallback: flat SVG of the same features with the same tooltips. */
function svgMap(el, opts) {
  const W = 1000;
  const H = 560;
  const coords = [];
  const walk = (c) => (typeof c[0] === "number" ? coords.push(c) : c.forEach(walk));
  opts.geojson.features.forEach((f) => walk(f.geometry.coordinates));
  const xs = coords.map((c) => c[0]);
  const ys = coords.map((c) => c[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const k = Math.cos(((minY + maxY) / 2) * (Math.PI / 180));
  const scale = Math.min((W - 60) / Math.max((maxX - minX) * k, 1e-9), (H - 90) / Math.max(maxY - minY, 1e-9));
  const px = (c) => [30 + (c[0] - minX) * k * scale, H - 50 - (c[1] - minY) * scale];
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.style.width = "100%";
  svg.style.height = "100%";
  const tip = h("div", { class: "map-tip card", style: { position: "absolute", display: "none", padding: "10px 12px", maxWidth: "300px", fontSize: "13px", pointerEvents: "none", zIndex: 3 } });
  const accent = cssVar("--accent", "#2dd4bf");
  opts.geojson.features.forEach((feature) => {
    const props = feature.properties || {};
    const fill = opts.color ? opts.color(props) : accent;
    const g = feature.geometry;
    let shape;
    if (g.type === "Point") {
      const [x, y] = px(g.coordinates);
      shape = document.createElementNS(ns, "circle");
      shape.setAttribute("cx", x);
      shape.setAttribute("cy", y);
      shape.setAttribute("r", 7);
    } else {
      const rings = g.type === "Polygon" ? [g.coordinates[0]] : g.coordinates.map((p) => p[0]);
      shape = document.createElementNS(ns, "path");
      shape.setAttribute("d", rings.map((ring) => "M" + ring.map((c) => px(c).map((v) => v.toFixed(1)).join(",")).join("L") + "Z").join(""));
      shape.setAttribute("fill-opacity", "0.7");
    }
    shape.setAttribute("fill", fill);
    shape.setAttribute("stroke", cssVar("--bg", "#071013"));
    shape.style.cursor = "pointer";
    shape.addEventListener("mousemove", (event) => {
      const node = tooltipNode(opts.tooltip?.(props));
      if (!node) return;
      tip.replaceChildren(node);
      const box = el.getBoundingClientRect();
      tip.style.display = "block";
      tip.style.left = `${Math.min(event.clientX - box.left + 14, box.width - 310)}px`;
      tip.style.top = `${Math.max(event.clientY - box.top - 10, 8)}px`;
    });
    shape.addEventListener("mouseleave", () => (tip.style.display = "none"));
    shape.addEventListener("click", () => opts.onClick?.(props));
    svg.append(shape);
  });
  el.replaceChildren(svg, tip, h("div", { class: "map-note" }, "Offline map: no basemap"));
  return { kind: "svg", map: null, setData: (geojson) => svgMap(el, { ...opts, geojson }) };
}
