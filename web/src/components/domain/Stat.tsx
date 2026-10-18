import type { ReactNode } from "react";
import { Tip } from "@/components/ui/Tooltip";

export function Stat({ label, value, sub, help, tone }: { label: string; value: ReactNode; sub?: ReactNode; help?: string; tone?: "red" | "amber" | "emerald" }) {
  const c = tone === "red" ? "text-red" : tone === "amber" ? "text-amber" : tone === "emerald" ? "text-emerald" : "text-fg";
  return (
    <div className="surface px-4 py-3">
      <div className="label flex items-center gap-1">{label}{help && <Tip text={help} />}</div>
      <div className={`num mt-1.5 text-[22px] font-semibold leading-none tracking-tight ${c}`}>{value}</div>
      {sub && <div className="mt-1.5 text-xs text-fg-3">{sub}</div>}
    </div>
  );
}
