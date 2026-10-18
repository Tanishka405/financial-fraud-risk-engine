import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Info } from "lucide-react";
import { useDataset, useGraph, useSummary } from "@/api/hooks";
import { NetworkGraph } from "@/features/network/NetworkGraph";
import { VolumeChart } from "@/components/charts/VolumeChart";
import { SeverityDistribution } from "@/components/charts/SeverityDistribution";
import { AccountLink, RiskBar, RuleBadge, SeverityBadge, typeLabel } from "@/components/domain/badges";
import { Stat } from "@/components/domain/Stat";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, PageHeader } from "@/components/ui/Card";
import { Segmented } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { Callout, EmptyState, ErrorState } from "@/components/ui/States";
import { dt, dateOnly, inr, inrCompact, int } from "@/lib/format";

export default function Overview() {
  const sum = useSummary();
  const ds = useDataset();
  const g = useGraph({ limit_nodes: 40, mode: "aggregated" });
  const [metric, setMetric] = useState<"value" | "count">("value");
  if (sum.isError) return <ErrorState error={sum.error} onRetry={() => void sum.refetch()} />;
  const s = sum.data, d = ds.data;
  const k = s?.kpis;
  return (
    <>
      <PageHeader title="Risk Intelligence"
        subtitle={d?.loaded ? `${d.name} · ${dateOnly(d.window_start)} – ${dateOnly(d.window_end)} · analysed ${dt(d.analysis_completed_at)}` : undefined}
        actions={d?.is_synthetic ? <Badge tone="amber">Synthetic data</Badge> : d?.loaded ? <Badge tone="emerald">Uploaded CSV</Badge> : null} />
      {d?.is_synthetic && <Callout tone="warn" className="mb-4" title="Synthetic, deterministic demo data">Alerts show detection of <b>injected test scenarios</b>, not real-world fraud. No accuracy claim is made for real data.</Callout>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {!k ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[88px]" />) : (<>
          <Stat label="Transactions" value={int(k.total_transactions)} sub="validated & analysed" />
          <Stat label="Accounts" value={int(k.total_accounts)} sub="distinct senders/receivers" />
          <Stat label="Total value" value={inrCompact(k.total_value_inr)} sub={inr(k.total_value_inr)} />
          <Stat label="Suspicious accounts" value={int(k.suspicious_accounts)} tone={k.suspicious_accounts ? "amber" : undefined} sub="with an alert, for review" help="Accounts matching at least one rule, or flagged only as a statistical outlier by the model." />
          <Stat label="Alerts" value={int(k.alerts)} sub={<Link to="/alerts" className="text-cyan hover:underline">Open queue</Link>} />
          <Stat label="Rejected records" value={int(k.rejected_records)} sub={<Link to="/data" className="text-cyan hover:underline">Validation report</Link>} />
        </>)}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Transaction activity" subtitle={s ? `Per ${s.time_series.bucket}, IST` : undefined}
            right={<Segmented label="Metric" value={metric} onChange={setMetric} options={[{ value: "value", label: "Value" }, { value: "count", label: "Count" }]} />} />
          <div className="px-2 pb-3">{s ? <VolumeChart points={s.time_series.points} bucket={s.time_series.bucket} metric={metric} /> : <Skeleton className="m-2 h-64" />}</div>
        </Card>
        <Card>
          <CardHeader title="Alert severity" subtitle="Ordinal index bands — not probabilities" />
          <div className="px-4 pb-4">
            {!s ? <Skeleton className="h-32" /> : s.kpis.alerts === 0 ? <EmptyState icon={<Info className="size-5" />} title="No alerts generated" body="No rule matched and no account was a model outlier in this dataset." className="py-6" /> : <SeverityDistribution data={s.severity_distribution} />}
            {s && s.by_type.length > 0 && (<>
              <div className="label mb-2 mt-5">By transaction type</div>
              <ul className="space-y-1">{s.by_type.map((t) => (<li key={t.transaction_type} className="flex justify-between text-xs"><span className="text-fg-2">{typeLabel(t.transaction_type)}</span><span className="num text-fg-3">{int(t.count)} · {inrCompact(t.value_inr)}</span></li>))}</ul>
            </>)}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader title="Recent alerts" subtitle="Most recent account activity first" right={<Link to="/alerts" className="flex items-center gap-1 text-xs text-cyan hover:underline">All alerts <ArrowRight className="size-3" /></Link>} />
          {!s ? <Skeleton className="m-4 h-48" /> : s.recent_alerts.length === 0 ? <EmptyState title="No alerts" body="Nothing to review." className="py-8" /> : (
            <ul className="divide-y divide-line">
              {s.recent_alerts.map((a) => (
                <li key={a.alert_id}><Link to={`/alerts/${a.alert_id}`} className="flex items-start gap-3 px-4 py-2.5 hover:bg-s3/60">
                  <SeverityBadge severity={a.severity} className="mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-mono text-xs text-fg">{a.account_id}</span>{a.reason_codes.map((c) => <RuleBadge key={c} code={c} />)}</div>
                    <p className="mt-0.5 truncate text-xs text-fg-3">{a.summary}</p>
                  </div>
                  <div className="text-right"><div className="num text-xs text-fg-2">Risk {a.risk_score.toFixed(1)}</div><div className="num text-2xs text-fg-3">{a.max_evidence_amount_inr ? `${inrCompact(a.max_evidence_amount_inr)} · ` : ""}{dt(a.last_activity_at)}</div></div>
                </Link></li>))}
            </ul>)}
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader title="Highest-risk accounts" subtitle="By combined risk index" />
          {!s ? <Skeleton className="m-4 h-48" /> : (
            <table className="w-full text-[13px]"><thead><tr className="text-left"><th className="label px-4 py-1.5">Account</th><th className="label px-2 py-1.5">Risk</th><th className="label px-4 py-1.5 text-right">Txns</th></tr></thead>
              <tbody className="divide-y divide-line">{s.top_risk_accounts.map((a) => (
                <tr key={a.account_id} className="hover:bg-s3/60"><td className="px-4 py-1.5"><AccountLink id={a.account_id} /></td><td className="px-2 py-1.5"><RiskBar value={a.risk_score} severity={a.alert_id ? a.severity : null} /></td><td className="num px-4 py-1.5 text-right text-fg-2">{int(a.txn_count)}</td></tr>))}</tbody></table>)}
          <div className="border-t border-line px-4 py-2 text-2xs text-fg-3">Most active: {s?.most_active_accounts.slice(0, 3).map((a) => `${a.account_id} (${int(a.txn_count)})`).join(" · ")}</div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2 overflow-hidden">
          <CardHeader title="Network preview" subtitle="Highest-risk accounts and the flows between them" right={<Link to="/network" className="flex items-center gap-1 rounded-md border border-line-strong bg-s3 px-2.5 py-1 text-xs text-fg hover:bg-s4">Open Network Intelligence <ArrowRight className="size-3" /></Link>} />
          <div className="relative h-80 border-t border-line">
            {g.data && g.data.nodes.length > 0 ? <NetworkGraph graph={g.data} interactive={false} showLabels={false} /> : g.isError ? <ErrorState error={g.error} /> : g.isLoading ? <Skeleton className="m-4 h-72" /> : <EmptyState title="No network to show" className="py-16" />}
            <Link to="/network" aria-label="Open the full network explorer" className="absolute inset-0" />
          </div>
        </Card>
        <Card>
          <CardHeader title="Dataset & analysis" />
          <dl className="space-y-2 px-4 pb-4 text-[13px]">
            {[["Source", d?.source === "synthetic" ? `Synthetic (seed ${d.seed})` : "CSV upload"], ["Accepted", int(d?.accepted)], ["Rejected", int(d?.rejected)],
              ["Window", `${dateOnly(d?.window_start)} – ${dateOnly(d?.window_end)}`], ["Analysed", dt(d?.analysis_completed_at)],
              ["Isolation Forest", d?.model_ran ? "Ran (deterministic seed)" : "Not run"]].map(([a, b]) => (
              <div key={a} className="flex justify-between gap-3"><dt className="text-fg-3">{a}</dt><dd className="num text-right text-fg-2">{b}</dd></div>))}
            {d?.notes.map((n) => <p key={n} className="rounded border border-amber/25 bg-amber/5 px-2 py-1.5 text-xs text-fg-2">{n}</p>)}
          </dl>
        </Card>
      </div>
    </>
  );
}
