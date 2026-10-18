import { Link } from "react-router-dom";
import type { RuleMatch } from "@/api/types";
import { RuleBadge, SignalKind } from "@/components/domain/badges";
import { inr, num, titleCase } from "@/lib/format";

const SKIP = new Set(["evidence_truncated", "loop", "chain", "amounts_inr"]);
function fmtVal(k: string, v: unknown): string {
  if (typeof v === "number") return k.endsWith("_inr") ? inr(v) : k.includes("p_value") ? v.toExponential(2) : Number.isInteger(v) ? String(v) : num(v, 2);
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v ?? "—");
}
export function RuleMatchCard({ m, onTxn }: { m: RuleMatch; onTxn?: (id: string) => void }) {
  return (
    <div className="rounded-lg border border-line bg-s2/60 p-3">
      <div className="flex flex-wrap items-center gap-2"><RuleBadge code={m.rule_code} /><SignalKind kind="rule" /><span className="text-2xs text-fg-3">role: {m.role} · weight {m.weight.toFixed(2)}</span></div>
      <p className="mt-2 text-[13px] text-fg">{m.summary}</p>
      <p className="mt-1 text-xs text-fg-3">{m.description}</p>
      <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        {Object.entries(m.metrics).filter(([k]) => !SKIP.has(k)).map(([k, v]) => (<div key={k} className="min-w-0"><dt className="truncate text-fg-3">{titleCase(k.replace(/_inr$/, ""))}</dt><dd className="num truncate text-fg-2">{fmtVal(k, v)}</dd></div>))}
      </dl>
      {m.transaction_ids.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-2xs"><span className="text-fg-3">Evidence:</span>
          {m.transaction_ids.slice(0, 8).map((t) => onTxn ? <button key={t} onClick={() => onTxn(t)} className="font-mono text-fg-2 hover:text-cyan">{t}</button> : <Link key={t} to={`/transactions?q=${t}`} className="font-mono text-fg-2 hover:text-cyan">{t}</Link>)}
          {m.transaction_ids.length > 8 && <span className="text-fg-3">+{m.transaction_ids.length - 8} more</span>}
          {m.metrics.evidence_truncated === true && <span className="text-amber">(evidence list capped)</span>}
        </div>)}
    </div>
  );
}
