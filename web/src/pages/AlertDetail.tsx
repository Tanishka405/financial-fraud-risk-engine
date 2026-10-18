import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, MessageSquarePlus } from "lucide-react";
import { useAddNote, useAlert, useGraph, useSetStatus } from "@/api/hooks";
import type { CaseStatus, Resolution } from "@/api/types";
import { AccountLink, RiskBar, RuleBadge, SeverityBadge, SignalKind, StatusBadge, TxnLink, typeLabel } from "@/components/domain/badges";
import { RuleMatchCard } from "@/components/domain/RuleMatchCard";
import { TransactionDrawer } from "@/components/domain/TransactionDrawer";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { Callout, ErrorState } from "@/components/ui/States";
import { Tip } from "@/components/ui/Tooltip";
import { useToast } from "@/components/ui/Toast";
import { NetworkGraph } from "@/features/network/NetworkGraph";
import { dt, inr, inrCompact, int, num } from "@/lib/format";
import { HELP, RESOLUTION_LABEL, STATUS } from "@/lib/tokens";

export default function AlertDetailPage() {
  const { alertId } = useParams();
  const q = useAlert(alertId);
  const acct = q.data?.account_id;
  const g = useGraph({ center: acct, depth: 1, limit_nodes: 40, mode: "aggregated" }, !!acct);
  const setStatus = useSetStatus(alertId ?? ""); const addNote = useAddNote(alertId ?? "");
  const { toast } = useToast();
  const [txn, setTxn] = useState<string | null>(null);
  const [pending, setPending] = useState<CaseStatus | null>(null); const [resolution, setResolution] = useState<Resolution | "">("");
  const [note, setNote] = useState("");

  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <div className="space-y-3"><Skeleton className="h-9 w-80" /><Skeleton className="h-72" /></div>;
  const a = q.data, c = a.case;
  const confirm = () => {
    if (!pending) return;
    if (pending === "closed" && !resolution) return;
    setStatus.mutate({ status: pending, resolution: pending === "closed" ? (resolution as Resolution) : undefined }, {
      onSuccess: () => { toast("success", `Status changed to ${STATUS[pending].label}.`); setPending(null); setResolution(""); },
      onError: (e) => { toast("error", e.message); setPending(null); } });
  };
  const submitNote = () => { const t = note.trim(); if (!t) return; addNote.mutate(t, { onSuccess: () => { setNote(""); toast("success", "Note saved."); }, onError: (e) => toast("error", e.message) }); };
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 flex items-center gap-1 text-xs text-fg-3"><Link to="/alerts" className="hover:text-fg-2">Alerts</Link><ChevronRight className="size-3" /><span className="font-mono text-fg-2">{a.alert_id}</span></nav>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div><div className="flex flex-wrap items-center gap-2.5"><h1 className="font-mono text-xl font-semibold">{a.account_id}</h1><SeverityBadge severity={a.severity} /><StatusBadge status={c.status} resolution={c.resolution} /></div>
          <p className="mt-1.5 max-w-3xl text-[13px] text-fg-2">{a.summary}</p>
          <p className="mt-1 text-xs text-fg-3">Generated {dt(a.generated_at)} · last account activity {dt(a.last_activity_at)}</p></div>
        <div className="flex gap-2"><Link to={`/accounts/${a.account_id}`}><Button>Account</Button></Link><Link to={`/network?account=${a.account_id}`}><Button>Network</Button></Link></div>
      </div>
      <Callout tone="info" className="mb-4" title="This is a lead, not a finding">{a.explanation.disclaimer}{a.is_synthetic_data && " This dataset is synthetic: matches reflect injected test patterns."}</Callout>

      <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-4">
          <Card><CardHeader title="Why this alert was generated" subtitle="Every contributing signal, with the values that triggered it" />
            <div className="px-4 pb-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-line bg-s2/60 p-3"><div className="label flex items-center gap-1">Risk index <Tip text={HELP.risk_score} /></div><div className="mt-1.5"><RiskBar value={a.risk_score} severity={a.severity} /></div></div>
                <div className="rounded-lg border border-line bg-s2/60 p-3"><div className="label flex items-center gap-1">Rule score <Tip text={HELP.rule_score} /></div><div className="num mt-1 text-lg font-semibold">{num(a.rule_score)}</div></div>
                <div className="rounded-lg border border-line bg-s2/60 p-3"><div className="label flex items-center gap-1">Model percentile <Tip text={HELP.model_score} /></div><div className="num mt-1 text-lg font-semibold">{a.model_score == null ? "n/a" : num(a.model_score)}</div></div>
              </div>
              <p className="mt-3 font-mono text-xs text-fg-3">{a.explanation.formula}</p>
              <p className="mt-1 text-xs text-fg-3">Severity bands on the index: critical ≥ {a.explanation.severity_bands.critical}, high ≥ {a.explanation.severity_bands.high}, medium ≥ {a.explanation.severity_bands.medium}. Basis: <span className="font-mono">{a.basis}</span>.</p>
              {a.explanation.rule_score_breakdown.length > 0 && (<div className="mt-3 flex flex-wrap gap-1.5">{a.explanation.rule_score_breakdown.map((b) => <span key={b.rule_code} className="flex items-center gap-1.5 text-xs text-fg-3"><RuleBadge code={b.rule_code} />w {b.weight.toFixed(2)}</span>)}</div>)}
            </div></Card>

          <Card><CardHeader title="Rule matches" right={<SignalKind kind="rule" />} />
            <div className="space-y-2.5 px-4 pb-4">{a.rule_matches.length === 0 ? <p className="text-[13px] text-fg-3">No AML-style rule matched. This alert comes solely from the Isolation Forest ranking this account as a statistical outlier — a weaker signal.</p> : a.rule_matches.map((m, i) => <RuleMatchCard key={i} m={m} onTxn={setTxn} />)}</div></Card>

          <Card><CardHeader title="Model signal & account features" right={<SignalKind kind="model" />} subtitle={a.explanation.model.meaning} />
            <div className="grid gap-4 px-4 pb-4 md:grid-cols-2">
              <div><h4 className="label mb-1.5 flex items-center gap-1">Most atypical features <Tip text={HELP.robust_z} /></h4>
                <table className="w-full text-xs"><tbody className="divide-y divide-line">{a.feature_deviations.map((f) => (<tr key={f.feature}><td className="py-1.5 font-mono text-fg-2">{f.feature}</td><td className="num py-1.5 text-right text-fg">{f.value}</td><td className="num py-1.5 text-right text-amber">z {f.robust_z}</td></tr>))}</tbody></table></div>
              <dl className="space-y-1.5 text-xs">{[["Sent", `${int(a.account_features.txn_count_sent)} txns · ${inr(a.account_features.total_amount_sent_inr)}`], ["Received", `${int(a.account_features.txn_count_received)} txns · ${inr(a.account_features.total_amount_received_inr)}`], ["Unique receivers", int(a.account_features.unique_counterparties_sent)], ["Max daily txns", int(a.account_features.max_daily_txn_count)], ["Inflow ÷ outflow", a.account_features.inflow_outflow_ratio == null ? "pure sink" : num(a.account_features.inflow_outflow_ratio, 2)]].map(([k, v]) => (<div key={k} className="flex justify-between gap-3"><dt className="text-fg-3">{k}</dt><dd className="num text-right text-fg-2">{v}</dd></div>))}</dl>
            </div></Card>

          <Card><CardHeader title="Related transactions" subtitle={`Evidence cited by the rules · ${int(a.related_transactions_total)} total${a.related_transactions_total > a.related_transactions.length ? `, showing ${a.related_transactions.length}` : ""}`} />
            {a.related_transactions.length === 0 ? <p className="px-4 pb-4 text-[13px] text-fg-3">No individual transactions are cited (model-only alert).</p> : (
              <div className="max-h-96 overflow-auto"><table className="w-full min-w-[640px] text-[13px]"><tbody className="divide-y divide-line">{a.related_transactions.map((t) => (
                <tr key={t.transaction_id}><td className="px-4 py-1.5"><TxnLink id={t.transaction_id} onOpen={setTxn} /></td><td className="px-2 py-1.5"><AccountLink id={t.sender_account_id} /> <span className="text-fg-3">→</span> <AccountLink id={t.receiver_account_id} /></td>
                  <td className="num px-2 py-1.5 text-right text-fg">{inr(t.amount_inr)}</td><td className="num px-2 py-1.5 text-fg-3">{dt(t.timestamp)}</td><td className="px-4 py-1.5 text-fg-3">{typeLabel(t.transaction_type)}</td></tr>))}</tbody></table></div>)}</Card>
        </div>

        <div className="space-y-4">
          <Card><CardHeader title="Case status" subtitle="Saved to the backend, per dataset" />
            <div className="px-4 pb-4">
              <ol className="mb-3 flex items-center gap-1.5 text-2xs" aria-label="Workflow">{(Object.keys(STATUS) as CaseStatus[]).map((s, i) => (<li key={s} className="flex items-center gap-1.5">{i > 0 && <span className="text-fg-3">→</span>}<span className={`rounded px-1.5 py-0.5 ${c.status === s ? `${STATUS[s].bg} ${STATUS[s].text} font-semibold` : "text-fg-3"}`}>{STATUS[s].label}</span></li>))}</ol>
              {c.status === "closed" && c.resolution && <p className="mb-3 text-xs text-fg-2">Resolution: {RESOLUTION_LABEL[c.resolution]}</p>}
              <div className="flex flex-wrap gap-2">{c.allowed_transitions.map((s) => (<Button key={s} size="sm" variant={s === "closed" ? "secondary" : "primary"} onClick={() => { setResolution(""); setPending(s); }}>{c.status === "closed" ? "Reopen" : s === "closed" ? "Close alert" : s === "under_review" ? "Start review" : "Set to open"}</Button>))}</div>
              {c.history.length > 0 && <ul className="mt-4 space-y-1.5 border-t border-line pt-3 text-xs text-fg-3">{c.history.map((h) => <li key={h.id}>{dt(h.created_at)} · {h.from_status} → <span className="text-fg-2">{h.to_status}</span></li>)}</ul>}
            </div></Card>
          <Card><CardHeader title="Investigator notes" subtitle="No authentication: notes carry no user identity" />
            <div className="px-4 pb-4">
              <label className="sr-only" htmlFor="note">Add a note</label>
              <textarea id="note" value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Record what you checked and why…" className="w-full resize-y rounded-md border border-line-strong bg-s2 px-2.5 py-2 text-[13px] placeholder:text-fg-3 focus:border-cyan focus:outline-none focus:ring-1 focus:ring-cyan/40" />
              <div className="mt-2 flex items-center justify-between"><span className="num text-2xs text-fg-3">{note.length}/2000</span><Button size="sm" variant="primary" disabled={!note.trim()} loading={addNote.isPending} onClick={submitNote}><MessageSquarePlus className="size-3.5" />Add note</Button></div>
              {c.notes.length === 0 ? <p className="mt-3 text-xs text-fg-3">No notes yet.</p> : <ul className="mt-3 space-y-2">{[...c.notes].reverse().map((n) => (<li key={n.id} className="rounded-md border border-line bg-s2/60 p-2.5"><p className="whitespace-pre-wrap text-[13px] text-fg">{n.body}</p><p className="num mt-1 text-2xs text-fg-3">{dt(n.created_at)}</p></li>))}</ul>}
            </div></Card>
          <Card className="overflow-hidden"><CardHeader title="Network context" subtitle="Direct counterparties" right={<Link to={`/network?account=${a.account_id}&depth=2`} className="text-xs text-cyan hover:underline">Explore →</Link>} />
            <div className="h-64 border-y border-line">{g.data && g.data.nodes.length > 0 ? <NetworkGraph graph={g.data} interactive={false} showLabels /> : <Skeleton className="m-3 h-56" />}</div>
            <ul className="divide-y divide-line">{a.network_context.top_counterparties.slice(0, 6).map((p) => (<li key={p.account_id} className="flex items-center justify-between gap-2 px-4 py-1.5"><div className="flex items-center gap-2"><AccountLink id={p.account_id} />{p.has_alert && <SeverityBadge severity={p.severity} />}</div><span className="num text-2xs text-fg-3">{p.txn_count} · {inrCompact(p.total_amount_inr)}</span></li>))}</ul></Card>
        </div>
      </div>

      <ConfirmDialog open={!!pending} title={pending === "closed" ? "Close this alert?" : pending === "open" && c.status === "closed" ? "Reopen this alert?" : `Change status to “${pending ? STATUS[pending].label : ""}”?`}
        confirmLabel="Confirm" confirmDisabled={pending === "closed" && !resolution} loading={setStatus.isPending} onCancel={() => setPending(null)} onConfirm={confirm}>
        <p>This is recorded in the case history for this dataset and cannot be deleted.</p>
        {pending === "closed" && (<div className="mt-3"><label htmlFor="res" className="label">Resolution (required)</label>
          <Select id="res" className="mt-1" value={resolution} onChange={(e) => setResolution(e.target.value as Resolution)}><option value="">Select…</option>{c.resolutions.map((r) => <option key={r} value={r}>{RESOLUTION_LABEL[r]}</option>)}</Select>
          <p className="mt-1.5 text-2xs text-fg-3">There is deliberately no “confirmed fraud” outcome: this tool produces leads for human review only.</p></div>)}
      </ConfirmDialog>
      {txn && <TransactionDrawer id={txn} onClose={() => setTxn(null)} onOpen={setTxn} />}
    </>
  );
}
