// Number and text formatting. Pure functions (no DOM), unit-tested in web/tests/.

const MONEY_KEY = /(usd|cost|price|total|revenue|profit|saving|amount|incentive|budget|fee|spend|difference|overcharge|refund)/i;
const PCT_KEY = /(pct|percent|rate|share|ratio|margin)/i;

export function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function number(value, digits = null) {
  if (!isNumber(value)) return value == null ? "—" : String(value);
  const d = digits ?? (Number.isInteger(value) ? 0 : Math.abs(value) >= 100 ? 0 : 2);
  return value.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function money(value, { currency = "USD", digits = null } = {}) {
  if (!isNumber(value)) return value == null ? "—" : String(value);
  const d = digits ?? (Math.abs(value) >= 1000 ? 0 : 2);
  return value.toLocaleString("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

/** 0.256 -> "25.6%"; values above 1 are treated as already in percent (25.6 -> "25.6%"). */
export function pct(value, digits = 1) {
  if (!isNumber(value)) return value == null ? "—" : String(value);
  const p = Math.abs(value) <= 1 ? value * 100 : value;
  return `${p.toFixed(digits).replace(/\.0+$/, "")}%`;
}

/** 1234567 -> "1.2M" for big headline numbers. */
export function compact(value) {
  if (!isNumber(value)) return value == null ? "—" : String(value);
  return value.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 1 });
}

/** "computed_total" -> "Computed total"; "co2Tons" -> "Co2 tons". */
export function humanize(key) {
  const words = String(key)
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Format a metric by its name: money-like keys get $, rate-like keys get %, else plain. */
export function metric(key, value) {
  if (!isNumber(value)) return value == null ? "—" : typeof value === "boolean" ? (value ? "Yes" : "No") : String(value);
  if (PCT_KEY.test(key) && Math.abs(value) <= 1) return pct(value);
  if (MONEY_KEY.test(key)) return money(value);
  return number(value);
}

/** Any JSON value as short display text. */
export function display(value) {
  if (value == null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (isNumber(value)) return number(value);
  if (Array.isArray(value)) return value.length ? value.map(display).join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function plural(n, word, many = `${word}s`) {
  return `${number(n)} ${n === 1 ? word : many}`;
}

/** Seconds or milliseconds as "1.2 s" / "350 ms". */
export function duration(ms) {
  if (!isNumber(ms)) return "—";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
