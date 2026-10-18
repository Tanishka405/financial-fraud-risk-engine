import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowDownLeft, ArrowUpRight, Crosshair, Network as NetIcon, Search, X } from "lucide-react";
import { useAccount, useGraph, useSearch } from "@/api/hooks";
import type { GraphEdge, GraphNode, GraphParams } from "@/api/types";
import { Callout, EmptyState, ErrorState } from "@/components/ui/States";
import { RiskBar, RuleBadge, SeverityBadge } from "@/components/domain/badges";
import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { Field, Input, Segmented, Toggle } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tip } from "@/components/ui/Tooltip";
import { Legend } from "@/features/network/Legend";
import { NetworkGraph, edgeSummary } from "@/features/network/NetworkGraph";
import { useDebounced } from "@/lib/useDebounced";
import { dayToIso, inr, int, dt } from "@/lib/format";
import { HELP } from "@/lib/tokens";

export default function NetworkPage() {
  const [sp, setSp] = useSearchParams();
  const center = sp.get("account") ?? "";
  const depth = Number(sp.get("depth") ?? 1) as 1 | 2 | 3;
  const mode = (sp.get("mode") ?? "aggregated") as "aggregated" | "transactions";
  const setParam = (k: string, v: string | null) => setSp((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); return n; }, { replace: true });

  const [minAmt, setMinAmt] = useState(""); const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [onlyFlagged, setOnlyFlagged] = useState(false); const [limit, setLimit] = useState(40);
  const [text, setText] = useState(center); const [selected, setSelected] = useState<string | null>(center || null);
  const [hoverEdge, setHoverEdge] = useState<GraphEdge | null>(null); const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [showLegend, setShowLegend] = useState(false);
  const dText = useDebounced(text, 250); const dMin = useDebounced(minAmt);
  const sugg = useSearch(dText.trim());
  useEffect(() => { setText(center); if (center) setSelected(center); }, [center]);

  const params: GraphParams = useMemo(() => ({ center: center || undefined, depth: center ? depth : undefined, min_amount: dMin || undefined, from: dayToIso(from), to: dayToIso(to, true), mode, limit_nodes: limit, only_flagged: !center && onlyFlagged }),
    [center, depth, dMin, from, to, mode, limit, onlyFlagged]);
  const g = useGraph(params);
  const graph = g.data;
  const acct = useAccount(selected ?? undefined);
  const sel = graph?.nodes.find((n) => n.id === selected);
  const conns = useMemo(() => {
    if (!graph || !selected) return { inn: [] as GraphEdge[], out: [] as GraphEdge[] };
    return { inn: graph.edges.filter((e) => e.target === selected).sort((a, b) => b.total_amount_inr - a.total_amount_inr), out: graph.edges.filter((e) => e.source === selected).sort((a, b) => b.total_amount_inr - a.total_amount_inr) };
  }, [graph, selected]);
  const focus = (id: string) => { setParam("account", id); setSelected(id); };
  const reset = () => { setSp({}, { replace: true }); setMinAmt(""); setFrom(""); setTo(""); setOnlyFlagged(false); setSelected(null); setText(""); setLimit(40); };
  const hiDegree = useMemo(() => (graph ? [...graph.nodes].sort((a, b) => b.degree_total - a.degree_total).slice(0, 3).map((n) => n.id) : []), [graph]);
  const notFound = g.isError && (g.error as { code?: string }).code === "ACCOUNT_NOT_FOUND";

  return (
    <>
      <PageHeader title="Network Intelligence" subtitle="Directed account-to-account money flow. Select an account to inspect its connections, or focus on it to explore its neighbourhood." />
      <Card className="mb-3">
        <div className="flex flex-wrap items-end gap-3 p-3">
          <Field label="Focus account" className="relative w-52">
            <div className="relative"><Search className="pointer-events-none absolute left-2 top-2 size-3.5 text-fg-3" />
              <Input aria-label="Focus on account" className="pl-7" placeholder="ACC00005" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && text.trim()) focus(text.trim()); }} /></div>
            {dText.trim() && dText.trim() !== center && sugg.data && sugg.data.accounts.length > 0 && (
              <ul role="listbox" className="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-md border border-line-strong bg-s2 shadow-xl">
                {sugg.data.accounts.map((a) => (<li key={a.account_id}><button role="option" aria-selected="false" className="flex w-full items-center justify-between px-2.5 py-1.5 text-left hover:bg-s4" onClick={() => focus(a.account_id)}><span className="font-mono text-xs">{a.account_id}</span><SeverityBadge severity={a.severity} /></button></li>))}
              </ul>)}
          </Field>
          <Field label="Depth"><Segmented label="Graph depth" value={depth} onChange={(v) => setParam("depth", String(v))} options={[{ value: 1, label: "1 hop" }, { value: 2, label: "2" }, { value: 3, label: "3" }]} /></Field>
          <Field label="Edges"><Segmented label="Edge mode" value={mode} onChange={(v) => setParam("mode", v)} options={[{ value: "aggregated", label: "Aggregated" }, { value: "transactions", label: "Individual" }]} /></Field>
          <Field label="Min ₹" className="w-28"><Input type="number" min={0} aria-label="Minimum transaction amount" value={minAmt} onChange={(e) => setMinAmt(e.target.value)} /></Field>
          <Field label="From (IST)"><Input type="date" aria-label="From date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To (IST)"><Input type="date" aria-label="To date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          <Field label="Max nodes" className="w-24"><select aria-label="Maximum nodes" className="h-8 rounded-md border border-line-strong bg-s2 px-2 text-[13px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>{[25, 40, 80, 150, 300].map((n) => <option key={n} value={n}>{n}</option>)}</select></Field>
          {!center && <div className="pb-1.5"><Toggle checked={onlyFlagged} onChange={setOnlyFlagged} label="Alerted only" /></div>}
          <div className="ml-auto flex items-center gap-2 pb-0.5"><Toggle checked={showLegend} onChange={setShowLegend} label="Legend" /><Button variant="ghost" size="sm" onClick={reset}>Reset all</Button></div>
        </div>
        {depth > 1 && !center && <p className="px-3 pb-2 text-2xs text-fg-3">Depth applies when an account is in focus.</p>}
      </Card>

      {graph?.meta.truncated && (
        <Callout tone="warn" className="mb-3" title="Showing a limited view">
          {center ? `The neighbourhood has more accounts than the ${graph.meta.limit_nodes}-node limit; the highest-risk, best-connected were kept.` : `Showing the ${graph.meta.node_count} highest-risk accounts out of ${int(graph.meta.scope_nodes)}. Focus an account to explore its neighbourhood.`}
          {graph.mode === "transactions" && ` Individual-transaction view is capped at ${int(graph.meta.max_transaction_edges)} edges (largest by amount).`}
        </Callout>)}

      <div className="grid gap-3 xl:grid-cols-[1fr_22rem]">
        <Card className="relative h-[calc(100vh-17rem)] min-h-[520px] overflow-hidden">
          {notFound ? <EmptyState icon={<Crosshair className="size-5" />} title="Account not found" body={`“${center}” is not in the loaded dataset.`} action={<Button onClick={reset}>Show overview</Button>} />
            : g.isError ? <ErrorState error={g.error} onRetry={() => void g.refetch()} />
            : !graph ? <Skeleton className="m-4 h-[90%]" />
            : graph.nodes.length === 0 ? <EmptyState icon={<NetIcon className="size-5" />} title="No transactions in this view" body="No flows meet the current amount and date filters. Relax them to see the network." action={<Button onClick={reset}>Reset filters</Button>} />
            : <NetworkGraph graph={graph} selectedId={selected} onSelect={setSelected} onHoverEdge={setHoverEdge} onHoverNode={setHoverNode} minimap={graph.nodes.length > 30} />}
          {graph && graph.nodes.length > 0 && (
            <>
              <div className="pointer-events-none absolute left-3 bottom-3 z-10 flex flex-col gap-2">
                {showLegend && <div className="pointer-events-auto"><Legend mode={graph.mode} /></div>}
              </div>
              {(hoverEdge || hoverNode) && (
                <div className="pointer-events-none absolute left-3 top-14 z-10 w-64 rounded-lg border border-line-strong bg-s2/95 p-2.5 text-xs shadow-xl backdrop-blur">
                  {hoverNode ? (<><div className="font-mono text-fg">{hoverNode.id}</div><div className="mt-1 text-fg-3">{hoverNode.has_alert ? `${hoverNode.severity} alert · ` : ""}risk {hoverNode.risk_score?.toFixed(1)}</div>
                    <div className="num mt-1 text-fg-2">In {int(hoverNode.visible_in)} · {inr(hoverNode.visible_in_inr)}</div><div className="num text-fg-2">Out {int(hoverNode.visible_out)} · {inr(hoverNode.visible_out_inr)}</div></>)
                  : hoverEdge && (<><div className="font-mono text-fg">{hoverEdge.source} → {hoverEdge.target}</div><div className="num mt-1 text-fg-2">{edgeSummary(hoverEdge)}</div>
                    {hoverEdge.aggregated ? <div className="num text-fg-3">{dt(hoverEdge.first_at)} – {dt(hoverEdge.last_at)}</div> : <div className="num text-fg-3">{dt(hoverEdge.timestamp)} · {hoverEdge.transaction_type}</div>}
                    {hoverEdge.flagged && <div className="mt-1 text-amber">Cited as rule evidence</div>}</>)}
                </div>)}
              <div className="pointer-events-none absolute left-1/2 top-3.5 z-10 hidden -translate-x-1/2 text-2xs text-fg-3 sm:block">{int(graph.meta.node_count)} accounts · {int(graph.meta.edge_count)} edges · {int(graph.meta.transactions_represented)} txns</div>
            </>)}
        </Card>

        <Card className="max-h-[calc(100vh-17rem)] min-h-[300px] overflow-auto">
          {!selected ? (
            <EmptyState icon={<Crosshair className="size-5" />} title="Select an account" body="Click a node to see its metrics and connections. Hover for quick details."
              action={hiDegree.length > 0 && <div className="text-xs text-fg-3">Most connected here: {hiDegree.map((id) => <button key={id} className="mr-1.5 font-mono text-cyan hover:underline" onClick={() => setSelected(id)}>{id}</button>)}</div>} />
          ) : (
            <div className="p-4">
              <div className="flex items-start justify-between"><div><div className="label">Account</div><div className="font-mono text-base text-fg">{selected}</div></div><Button variant="ghost" size="sm" aria-label="Clear selection" onClick={() => setSelected(null)}><X className="size-4" /></Button></div>
              <div className="mt-2 flex items-center gap-2">{sel?.has_alert && <SeverityBadge severity={sel.severity} />}{sel?.reason_codes.map((c) => <RuleBadge key={c} code={c} />)}</div>
              <div className="mt-3 flex gap-2"><Button size="sm" variant="primary" onClick={() => focus(selected)} disabled={center === selected}><Crosshair className="size-3.5" />Focus neighbourhood</Button><Link to={`/accounts/${selected}`}><Button size="sm">Account details</Button></Link></div>
              {acct.isLoading ? <Skeleton className="mt-4 h-28" /> : acct.data && (
                <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2.5 text-xs">
                  <div><dt className="text-fg-3">Risk index <Tip text={HELP.risk_score} /></dt><dd className="mt-0.5"><RiskBar value={acct.data.scores.risk_score} severity={acct.data.alert?.severity} /></dd></div>
                  <div><dt className="text-fg-3">Model percentile <Tip text={HELP.model_score} /></dt><dd className="num mt-0.5 text-fg">{acct.data.scores.model_score?.toFixed(1) ?? "—"}</dd></div>
                  <div><dt className="text-fg-3">Sent</dt><dd className="num text-fg">{int(acct.data.observed.txn_count_sent)} · {inr(acct.data.observed.total_amount_sent_inr)}</dd></div>
                  <div><dt className="text-fg-3">Received</dt><dd className="num text-fg">{int(acct.data.observed.txn_count_received)} · {inr(acct.data.observed.total_amount_received_inr)}</dd></div>
                  <div><dt className="text-fg-3">Counterparties <Tip text={HELP.counterparties} /></dt><dd className="num text-fg">{int(acct.data.graph_metrics.unique_counterparties_total)}</dd></div>
                  <div><dt className="text-fg-3">Max daily txns <Tip text={HELP.max_daily} /></dt><dd className="num text-fg">{int(acct.data.computed_features.max_daily_txn_count)}</dd></div>
                  <div className="col-span-2"><dt className="text-fg-3">Inflow / outflow <Tip text={HELP.inflow_outflow} /></dt><dd className="num text-fg">{acct.data.computed_features.inflow_outflow_ratio?.toFixed(2) ?? acct.data.computed_features.inflow_outflow_ratio_note}</dd></div>
                </dl>)}
              {[["Incoming", conns.inn, ArrowDownLeft, "source"], ["Outgoing", conns.out, ArrowUpRight, "target"]].map(([label, list, Icon, key]) => {
                const I = Icon as typeof ArrowDownLeft; const L = list as GraphEdge[];
                return (<section key={label as string} className="mt-5"><h4 className="label mb-1.5 flex items-center gap-1"><I className="size-3" />{label as string} in this view ({L.length})</h4>
                  {L.length === 0 ? <p className="text-xs text-fg-3">None visible.</p> : (<ul className="divide-y divide-line rounded border border-line">{L.slice(0, 12).map((e) => (
                    <li key={e.id} className="flex items-center justify-between gap-2 px-2.5 py-1.5"><button className="font-mono text-xs text-cyan hover:underline" onClick={() => setSelected(e[key as "source" | "target"])}>{e[key as "source" | "target"]}</button><span className="num text-2xs text-fg-2">{edgeSummary(e)}</span></li>))}</ul>)}
                  {L.length > 12 && <p className="mt-1 text-2xs text-fg-3">+{L.length - 12} more</p>}</section>);
              })}
            </div>)}
        </Card>
      </div>
    </>
  );
}
