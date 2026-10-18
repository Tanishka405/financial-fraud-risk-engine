import type { Severity } from "@/api/types";
import { int } from "@/lib/format";
import { SEVERITY, SEVERITY_ORDER } from "@/lib/tokens";

export function SeverityDistribution({ data }: { data: Record<Severity, number> }) {
  const total = SEVERITY_ORDER.reduce((s, k) => s + (data[k] ?? 0), 0);
  if (total === 0) return null;
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-s4" role="img" aria-label={`Alerts by severity: ${SEVERITY_ORDER.map((k) => `${data[k] ?? 0} ${k}`).join(", ")}`}>
        {SEVERITY_ORDER.map((k) => (data[k] ?? 0) > 0 && <div key={k} className={SEVERITY[k].bar} style={{ width: `${((data[k] ?? 0) / total) * 100}%` }} />)}
      </div>
      <ul className="mt-3 space-y-1.5">
        {SEVERITY_ORDER.map((k) => (
          <li key={k} className="flex items-center justify-between text-[13px]">
            <span className="flex items-center gap-2 text-fg-2"><span className={`size-2 rounded-full ${SEVERITY[k].bar}`} />{SEVERITY[k].label}</span>
            <span className="num text-fg">{int(data[k] ?? 0)} <span className="text-fg-3">· {(((data[k] ?? 0) / total) * 100).toFixed(0)}%</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}
