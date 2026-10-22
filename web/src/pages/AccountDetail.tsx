import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Network } from "lucide-react";
import { useAccount } from "@/api/hooks";
import { AccountLink, RiskBar, SeverityBadge, SignalKind, StatusBadge, TxnLink, typeLabel } from "@/components/domain/badges";
import { RuleMatchCard } from "@/components/domain/RuleMatchCard";
import { TransactionDrawer } from "@/components/domain/TransactionDrawer";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, PageHeader } from "@/components/ui/Card";
import { GraphStructureCard } from "@/components/domain/GraphStructureCard";
import { ErrorState } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tip } from "@/components/ui/Tooltip";
import { axisTime, dt, inr, inrCompact, int, num } from "@/lib/format";
import { HELP } from "@/lib/tokens";

const Row = ({ k, v, help }: { k: string; v: React.ReactNode; help?: string }) => (
  <div className="flex items-baseline justify-between gap-3 py-1.5"><dt className="flex items-center gap-1 text-fg-3">{k}{help && <Tip text={help} />}</dt><dd className="num text-right text-fg">{v}</dd></div>
);

export default function AccountDetailPage() {
  const { accountId } = useParams();
  const q = useAccount(accountId);
  const [txn, setTxn] = useState<string | null>(null);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <div className="space-y-3"><Skeleton className="h-9 w-72" /><Skeleton className="h-64" /></div>;
  const d = q.data, o = d.observed, c = d.computed_features;
  const tl = d.timeline.points.map((p) => ({ ...p, sent: p.sent_amount_inr, received: p.received_amount_inr }));
  return (
    <>
      <PageHeader title={<span className="font-mono">{d.account_id}</span>}
        subtitle={<span className="flex flex-wrap items-center gap-2">First seen {dt(o.first_seen)} · last seen {dt(o.last_seen)}{d.alert && <><SeverityBadge severity={d.alert.severity} /><StatusBadge status={d.alert.status} /><Link className="text-cyan hover:underline" to={`/alerts/${d.alert.alert_id}`}>{d.alert.alert_id}</Link></>}</span>}
        actions={<Link to={`/network?account=${d.account_id}`}><Button variant="primary"><Network className="size-4" />Open in Network Intelligence</Button></Link>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card><CardHeader title="Observed facts" right={<SignalKind kind="observed" />} subtitle="Counted directly from transactions" />
          <dl className="divide-y divide-line px-4 pb-3 text-[13px]">
            <Row k="Transactions sent" v={int(o.txn_count_sent)} /><Row k="Transactions received" v={int(o.txn_count_received)} />
            <Row k="Total sent" v={inr(o.total_amount_sent_inr)} /><Row k="Total received" v={inr(o.total_amount_received_inr)} /></dl></Card>
        <Card><CardHeader title="Computed metrics" right={<SignalKind kind="computed" />} subtitle="Derived features & graph metrics" />
          <dl className="divide-y divide-line px-4 pb-3 text-[13px]">
            <Row k="Avg sent" v={inr(c.avg_amount_sent_inr)} /><Row k="Avg received" v={inr(c.avg_amount_received_inr)} />
            <Row k="Counterparties (total)" help={HELP.counterparties} v={int(d.graph_metrics.unique_counterparties_total)} />
            <Row k="Receivers / senders" v={`${int(c.unique_counterparties_sent)} / ${int(c.unique_counterparties_received)}`} />
            <Row k="Inflow ÷ outflow" help={HELP.inflow_outflow} v={c.inflow_outflow_ratio == null ? c.inflow_outflow_ratio_note ?? "—" : num(c.inflow_outflow_ratio, 2)} />
            <Row k="Max daily txns" help={HELP.max_daily} v={int(c.max_daily_txn_count)} /><Row k="Degree in / out" help={HELP.degree} v={`${int(d.graph_metrics.in_degree)} / ${int(d.graph_metrics.out_degree)}`} /></dl></Card>
        <Card><CardHeader title="Scores" subtitle="Kept separate on purpose" />
          <dl className="divide-y divide-line px-4 pb-3 text-[13px]">
            <Row k="Risk index" help={HELP.risk_score} v={<RiskBar value={d.scores.risk_score} severity={d.alert?.severity} />} />
            <Row k="Rule score" help={HELP.rule_score} v={num(d.scores.rule_score)} />
            <Row k="Model percentile" help={HELP.model_score} v={d.scores.model_score == null ? "model not run" : num(d.scores.model_score)} /></dl>
          <p className="px-4 pb-3 text-2xs text-fg-3">Ordinal index for review priority — not a probability of fraud.</p></Card>
      </div>

      <div className="mt-4"><GraphStructureCard g={d.graph_analytics} /></div>

      <Card className="mt-4"><CardHeader title="Activity timeline" subtitle={`Sent vs received value per ${d.timeline.bucket} (IST)`} />
        <div className="h-56 px-2 pb-3" role="img" aria-label="Sent and received value over time"><ResponsiveContainer width="100%" height="100%">
          <BarChart data={tl} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}><CartesianGrid stroke="#16223a" vertical={false} />
            <XAxis dataKey="t" tickFormatter={(v: string) => axisTime(v, d.timeline.bucket)} stroke="#6b7a95" fontSize={11} tickLine={false} axisLine={false} minTickGap={28} />
            <YAxis tickFormatter={inrCompact} width={64} stroke="#6b7a95" fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip cursor={{ fill: "#ffffff08" }} contentStyle={{ background: "#141e33", border: "1px solid #2a3a5c", borderRadius: 8, fontSize: 12 }} labelFormatter={(v) => axisTime(String(v), d.timeline.bucket)} formatter={(v, n) => [inr(Number(v)), n === "sent" ? "Sent" : "Received"]} />
            <Bar dataKey="received" fill="#34d399" radius={[2, 2, 0, 0]} isAnimationActive={false} /><Bar dataKey="sent" fill="#22d3ee" radius={[2, 2, 0, 0]} isAnimationActive={false} />
          </BarChart></ResponsiveContainer></div>
        <div className="flex gap-4 px-4 pb-3 text-2xs text-fg-3"><span><i className="mr-1 inline-block size-2 rounded-sm bg-cyan" />Sent</span><span><i className="mr-1 inline-block size-2 rounded-sm bg-emerald" />Received</span></div></Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card><CardHeader title="Rule matches" right={<SignalKind kind="rule" />} subtitle="Transparent patterns — leads, not verdicts" />
          <div className="space-y-2.5 px-4 pb-4">{d.rule_matches.length === 0 ? <p className="text-[13px] text-fg-3">No AML-style rule matched this account.</p> : d.rule_matches.map((m, i) => <RuleMatchCard key={i} m={m} onTxn={setTxn} />)}</div></Card>
        <Card><CardHeader title="Model signal" right={<SignalKind kind="model" />} subtitle={d.model_signal.note} />
          <div className="px-4 pb-4">{d.model_signal.model_score == null ? <p className="text-[13px] text-fg-3">The Isolation Forest did not run on this dataset (too few accounts or disabled).</p> : (<>
            <div className="num text-2xl font-semibold">{num(d.model_signal.model_score)}<span className="ml-1 text-sm font-normal text-fg-3">percentile</span></div>
            {d.model_signal.feature_deviations.length > 0 ? (<><h4 className="label mb-1.5 mt-4 flex items-center gap-1">Most atypical features <Tip text={HELP.robust_z} /></h4>
              <table className="w-full text-xs"><tbody className="divide-y divide-line">{d.model_signal.feature_deviations.map((f) => (<tr key={f.feature}><td className="py-1.5 font-mono text-fg-2">{f.feature}</td><td className="num py-1.5 text-right text-fg">{f.value}</td><td className="num py-1.5 text-right text-fg-3">median {f.population_median}</td><td className="num py-1.5 text-right text-amber">z {f.robust_z}</td></tr>))}</tbody></table></>)
              : <p className="mt-2 text-xs text-fg-3">Feature deviations are listed only for accounts that raised an alert.</p>}</>)}</div></Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card><CardHeader title="Top counterparties" subtitle="By total value exchanged" />
          <table className="w-full text-[13px]"><thead><tr className="text-left"><th className="label px-4 py-1.5">Account</th><th className="label px-2 py-1.5 text-right">Sent to</th><th className="label px-4 py-1.5 text-right">Received from</th></tr></thead>
            <tbody className="divide-y divide-line">{d.top_counterparties.map((p) => (<tr key={p.account_id}><td className="px-4 py-1.5"><div className="flex items-center gap-2"><AccountLink id={p.account_id} />{p.has_alert && <SeverityBadge severity={p.severity} />}</div></td>
              <td className="num px-2 py-1.5 text-right text-fg-2">{p.sent_count ? `${p.sent_count} · ${inrCompact(p.sent_amount_inr)}` : "—"}</td><td className="num px-4 py-1.5 text-right text-fg-2">{p.received_count ? `${p.received_count} · ${inrCompact(p.received_amount_inr)}` : "—"}</td></tr>))}</tbody></table></Card>
        <Card><CardHeader title="Recent transactions" /><div className="overflow-x-auto"><table className="w-full min-w-[480px] text-[13px]"><tbody className="divide-y divide-line">{d.recent_transactions.slice(0, 10).map((t) => (
          <tr key={t.transaction_id}><td className="px-4 py-1.5"><TxnLink id={t.transaction_id} onOpen={setTxn} /></td><td className="px-2 py-1.5 text-xs text-fg-3">{t.sender_account_id === d.account_id ? "→ " + t.receiver_account_id : "← " + t.sender_account_id}</td><td className="num px-2 py-1.5 text-right text-fg">{inr(t.amount_inr)}</td><td className="px-4 py-1.5 text-right text-xs text-fg-3">{typeLabel(t.transaction_type)}</td></tr>))}</tbody></table></div></Card>
      </div>
      {txn && <TransactionDrawer id={txn} onClose={() => setTxn(null)} onOpen={setTxn} />}
    </>
  );
}
