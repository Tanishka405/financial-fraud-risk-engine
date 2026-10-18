import { useEffect } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { useTransaction } from "@/api/hooks";
import { AccountLink, RiskBar, RuleBadge, typeLabel } from "@/components/domain/badges";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Skeleton";
import { dt, inr, int } from "@/lib/format";

export function TransactionDrawer({ id, onClose, onOpen }: { id: string; onClose: () => void; onOpen: (id: string) => void }) {
  const q = useTransaction(id);
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  const d = q.data, t = d?.transaction;
  return (
    <div className="fixed inset-0 z-[70]">
      <div className="absolute inset-0 bg-ink/60" onClick={onClose} />
      <aside role="dialog" aria-modal="true" aria-label="Transaction detail" className="absolute inset-y-0 right-0 w-full max-w-md overflow-auto border-l border-line-strong bg-s2 shadow-2xl animate-slide-in">
        <div className="flex items-center justify-between border-b border-line px-4 py-3"><div><div className="label">Transaction</div><div className="font-mono text-sm text-fg">{id}</div></div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}><X className="size-4" /></Button></div>
        {q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : !t ? <div className="space-y-3 p-4"><Skeleton className="h-6" /><Skeleton className="h-32" /></div> : (
          <div className="space-y-5 p-4 text-[13px]">
            <div className="num text-3xl font-semibold tracking-tight">{inr(t.amount_inr)}</div>
            <dl className="grid grid-cols-[7rem_1fr] gap-y-2">
              <dt className="text-fg-3">Sender</dt><dd><AccountLink id={t.sender_account_id} /> <span className="ml-2 inline-block align-middle"><RiskBar value={t.sender_risk} /></span></dd>
              <dt className="text-fg-3">Receiver</dt><dd><AccountLink id={t.receiver_account_id} /> <span className="ml-2 inline-block align-middle"><RiskBar value={t.receiver_risk} /></span></dd>
              <dt className="text-fg-3">Time</dt><dd className="num">{dt(t.timestamp)}</dd>
              <dt className="text-fg-3">Type</dt><dd>{typeLabel(t.transaction_type)}</dd>
              <dt className="text-fg-3">Rules citing it</dt><dd className="flex flex-wrap gap-1">{d.flagged_rules.length ? d.flagged_rules.map((c) => <RuleBadge key={c} code={c} />) : <span className="text-fg-3">None</span>}</dd>
              <dt className="text-fg-3">Alerts</dt><dd className="flex flex-wrap gap-1.5">{d.related_alert_ids.length ? d.related_alert_ids.map((a) => <Link key={a} to={`/alerts/${a}`} className="font-mono text-xs text-cyan hover:underline">{a}</Link>) : <span className="text-fg-3">None</span>}</dd>
            </dl>
            <p className="rounded border border-line bg-s3/50 px-2.5 py-2 text-xs text-fg-3">{d.note}</p>
            <section>
              <h4 className="label mb-2">Same sender → receiver pair · {int(d.same_pair.count)} txns · {inr(d.same_pair.total_amount_inr)}</h4>
              {d.same_pair.others.length === 0 ? <p className="text-xs text-fg-3">No other transactions between these accounts.</p> : (
                <ul className="divide-y divide-line rounded border border-line">{d.same_pair.others.map((o) => (<li key={o.transaction_id} className="flex justify-between px-2.5 py-1.5"><button className="font-mono text-xs text-fg-2 hover:text-cyan" onClick={() => onOpen(o.transaction_id)}>{o.transaction_id}</button><span className="num text-xs text-fg-2">{inr(o.amount_inr)}</span></li>))}</ul>)}
            </section>
            <section>
              <h4 className="label mb-2">Closest in time from the same sender</h4>
              {d.sender_nearby.length === 0 ? <p className="text-xs text-fg-3">None.</p> : (
                <ul className="divide-y divide-line rounded border border-line">{d.sender_nearby.map((o) => (<li key={o.transaction_id} className="flex items-center justify-between gap-2 px-2.5 py-1.5"><button className="font-mono text-xs text-fg-2 hover:text-cyan" onClick={() => onOpen(o.transaction_id)}>{o.transaction_id}</button><span className="num text-2xs text-fg-3">{dt(o.timestamp)}</span><span className="num text-xs text-fg-2">{inr(o.amount_inr)}</span></li>))}</ul>)}
            </section>
            <Link to={`/network?account=${t.sender_account_id}`} className="inline-block text-xs text-cyan hover:underline">View sender in Network Intelligence →</Link>
          </div>)}
      </aside>
    </div>
  );
}
