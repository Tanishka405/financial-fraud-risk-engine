import { Link } from "react-router-dom";
import type { CaseStatus, Resolution, Severity } from "@/api/types";
import { cn } from "@/lib/cn";
import { RESOLUTION_LABEL, SEVERITY, STATUS } from "@/lib/tokens";
import { titleCase } from "@/lib/format";

export function SeverityBadge({ severity, className }: { severity: Severity | null | undefined; className?: string }) {
  if (!severity) return <span className="text-fg-3">—</span>;
  const s = SEVERITY[severity];
  return <span className={cn("inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-2xs font-semibold ring-1 ring-inset", s.text, s.bg, s.ring, className)}><span className={cn("size-1.5 rounded-full", s.bar)} />{s.label}</span>;
}
export function StatusBadge({ status, resolution }: { status: CaseStatus; resolution?: Resolution | null }) {
  const s = STATUS[status];
  return (
    <span title={resolution ? RESOLUTION_LABEL[resolution] : undefined} className={cn("inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-2xs font-medium", s.text, s.bg)}>
      <span className={cn("size-1.5 rounded-full", s.dot)} />{s.label}
    </span>
  );
}
export function RuleBadge({ code, className }: { code: string; className?: string }) {
  const model = code === "MODEL_ANOMALY";
  return <span className={cn("inline-flex whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium", model ? "border-cyan/25 bg-cyan/5 text-cyan" : "border-line-strong bg-s3 text-fg-2", className)}>{code}</span>;
}
export function SignalKind({ kind }: { kind: "observed" | "computed" | "rule" | "model" }) {
  const m = { observed: ["Observed fact", "text-emerald bg-emerald/10"], computed: ["Computed metric", "text-fg-2 bg-s4"], rule: ["Rule match", "text-amber bg-amber/10"], model: ["Model signal", "text-cyan bg-cyan/10"] }[kind];
  return <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider", m[1])}>{m[0]}</span>;
}
export const AccountLink = ({ id, className }: { id: string; className?: string }) => (
  <Link to={`/accounts/${encodeURIComponent(id)}`} className={cn("font-mono text-xs text-cyan hover:underline", className)} onClick={(e) => e.stopPropagation()}>{id}</Link>
);
export const TxnLink = ({ id, onOpen }: { id: string; onOpen?: (id: string) => void }) => (
  <button className="font-mono text-xs text-fg-2 hover:text-cyan hover:underline" onClick={(e) => { e.stopPropagation(); onOpen?.(id); }}>{id}</button>
);
export function RiskBar({ value, severity }: { value: number | null | undefined; severity?: Severity | null }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="flex items-center gap-2" role="img" aria-label={`Risk score ${v.toFixed(1)} of 100`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-s4"><div className={cn("h-full rounded-full", severity ? SEVERITY[severity].bar : "bg-slate-node")} style={{ width: `${v}%` }} /></div>
      <span className="num w-9 text-right text-xs text-fg-2">{value == null ? "—" : v.toFixed(1)}</span>
    </div>
  );
}
export const typeLabel = (t: string) => titleCase(t).replace("Upi", "UPI").replace("Neft", "NEFT").replace("Imps", "IMPS").replace("Rtgs", "RTGS");
