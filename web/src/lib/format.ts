/** INR + IST presentation. All timestamps from the API are ISO strings with an offset; we always render in IST. */
const TZ = "Asia/Kolkata";
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const intFmt = new Intl.NumberFormat("en-IN");
const dtParts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const dayParts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short", year: "numeric" });
const shortDay = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short" });
const hourFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

export const DASH = "—";

export function inr(n: number | null | undefined): string { return n == null || !Number.isFinite(n) ? DASH : inr2.format(n); }

/** Compact Indian-system notation (lakh / crore) for dense KPI tiles and axes. */
export function inrCompact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return DASH;
  const a = Math.abs(n);
  if (a >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return inr0.format(n);
}
export function int(n: number | null | undefined): string { return n == null ? DASH : intFmt.format(n); }
export function num(n: number | null | undefined, d = 1): string { return n == null || !Number.isFinite(n) ? DASH : n.toFixed(d); }

function valid(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}
/** "01 Jan 2024, 09:00 IST" */
export function dt(iso: string | null | undefined): string {
  const d = valid(iso); return d ? `${dtParts.format(d).replace(",", ",")} IST` : DASH;
}
export function dateOnly(iso: string | null | undefined): string { const d = valid(iso); return d ? dayParts.format(d) : DASH; }
export function axisTime(iso: string, bucket: "hour" | "day"): string {
  const d = valid(iso); return d ? (bucket === "hour" ? hourFmt.format(d) : shortDay.format(d)) : "";
}
/** Convert an <input type="date"> value (IST calendar day) to an API-ready ISO bound. */
export function dayToIso(day: string, end = false): string | undefined {
  if (!day) return undefined;
  return `${day}T${end ? "23:59:59" : "00:00:00"}+05:30`;
}
export function titleCase(code: string): string { return code.toLowerCase().split("_").map((w) => w[0]?.toUpperCase() + w.slice(1)).join(" "); }
export function pct(x: number | null | undefined, d = 1): string { return x == null ? DASH : `${(x * 100).toFixed(d)}%`; }
