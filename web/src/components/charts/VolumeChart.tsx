import type { TooltipContentProps } from "recharts";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisTime, inr, inrCompact, int } from "@/lib/format";

interface Pt { t: string; count: number; value_inr: number }
const ax = { stroke: "#6b7a95", fontSize: 11, tickLine: false, axisLine: false } as const;

export function VolumeChart({ points, bucket, metric }: { points: Pt[]; bucket: "hour" | "day"; metric: "value" | "count" }) {
  const key = metric === "value" ? "value_inr" : "count";
  const fmt = (v: number) => (metric === "value" ? inrCompact(v) : int(v));
  const tip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload as Pt;
    return (
      <div className="rounded-md border border-line-strong bg-s3 px-2.5 py-2 text-xs shadow-xl">
        <div className="mb-1 text-fg-3">{axisTime(p.t, bucket)}</div>
        <div className="num text-fg">{int(p.count)} transactions</div><div className="num text-fg-2">{inr(p.value_inr)}</div>
      </div>
    );
  };
  return (
    <div className="h-64" role="img" aria-label={`Transaction ${metric} over time`}>
      <ResponsiveContainer width="100%" height="100%">
        {metric === "value" ? (
          <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs><linearGradient id="vg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} /><stop offset="100%" stopColor="#22d3ee" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid stroke="#16223a" vertical={false} />
            <XAxis dataKey="t" tickFormatter={(v: string) => axisTime(v, bucket)} {...ax} minTickGap={28} />
            <YAxis tickFormatter={fmt} width={64} {...ax} />
            <Tooltip content={tip} cursor={{ stroke: "#2a3a5c" }} />
            <Area type="monotone" dataKey={key} stroke="#22d3ee" strokeWidth={1.6} fill="url(#vg)" isAnimationActive={false} />
          </AreaChart>
        ) : (
          <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#16223a" vertical={false} />
            <XAxis dataKey="t" tickFormatter={(v: string) => axisTime(v, bucket)} {...ax} minTickGap={28} />
            <YAxis tickFormatter={fmt} width={44} {...ax} />
            <Tooltip content={tip} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey={key} fill="#34d399" radius={[2, 2, 0, 0]} isAnimationActive={false} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
