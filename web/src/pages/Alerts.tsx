import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { useAlerts } from "@/api/hooks";
import type { CaseStatus, Severity } from "@/api/types";
import { AccountLink, RiskBar, RuleBadge, SeverityBadge, StatusBadge } from "@/components/domain/badges";
import { Card, PageHeader } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { SortTh, Th } from "@/components/ui/SortHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { SEVERITY, SEVERITY_ORDER, STATUS } from "@/lib/tokens";
import { useDebounced } from "@/lib/useDebounced";
import { dt, int } from "@/lib/format";

export default function Alerts() {
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [severity, setSeverity] = useState<Severity | "">(""); const [status, setStatus] = useState<CaseStatus | "">("");
  const [reason, setReason] = useState(""); const [sort, setSort] = useState("risk_score"); const [order, setOrder] = useState<"asc" | "desc">("desc"); const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const query = useAlerts({ page, page_size: 20, q: dq.trim() || undefined, severity: severity || undefined, status: status || undefined, reason: reason || undefined, sort, order });
  const fac = query.data?.facets;
  const rows = query.data?.items ?? [];
  const onSort = (f: string) => { if (f === sort) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(f); setOrder("desc"); } setPage(1); };
  const clear = () => { setQ(""); setSeverity(""); setStatus(""); setReason(""); setPage(1); };
  const any = q || severity || status || reason;
  return (
    <>
      <PageHeader title="Alerts & Investigations" subtitle="Accounts that matched transparent rules or ranked as statistical outliers. An alert is a lead for human review — not a confirmed fraud case." />
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by severity">
        {SEVERITY_ORDER.map((s) => (
          <button key={s} onClick={() => { setSeverity(severity === s ? "" : s); setPage(1); }} aria-pressed={severity === s}
            className={cn("flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-colors", severity === s ? "border-line-strong bg-s4" : "border-line bg-s2 hover:bg-s3")}>
            <span className={cn("size-2 rounded-full", SEVERITY[s].bar)} />{SEVERITY[s].label}<span className="num font-semibold text-fg">{int(fac?.severity[s] ?? 0)}</span></button>))}
      </div>
      <Card>
        <div className="flex flex-wrap items-end gap-3 border-b border-line p-4">
          <Field label="Search" className="w-60"><Input aria-label="Search alerts" placeholder="Account, alert ID, text…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
          <Field label="Status" className="w-40"><Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value as CaseStatus | ""); setPage(1); }}><option value="">All</option>{(Object.keys(STATUS) as CaseStatus[]).map((s) => <option key={s} value={s}>{STATUS[s].label} ({fac?.status[s] ?? 0})</option>)}</Select></Field>
          <Field label="Reason" className="w-60"><Select aria-label="Reason code" value={reason} onChange={(e) => { setReason(e.target.value); setPage(1); }}><option value="">All reasons</option>{Object.entries(fac?.reason ?? {}).map(([c, n]) => <option key={c} value={c}>{c} ({n})</option>)}</Select></Field>
          <Button variant="ghost" size="sm" disabled={!any} onClick={clear}>Clear filters</Button>
        </div>
        {query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.isLoading ? <TableSkeleton cols={6} /> : rows.length === 0 ? (
          <EmptyState icon={<Bell className="size-5" />} title={any ? "No alerts match these filters" : "No alerts in this dataset"} body={any ? "Clear or loosen the filters." : "No rule matched and no account was a model outlier. That is a valid outcome, not an error."} action={any ? <Button onClick={clear}>Clear filters</Button> : undefined} />
        ) : (
          <div className={cn("overflow-x-auto", query.isFetching && "opacity-60")}><table className="w-full min-w-[900px] text-[13px]">
            <thead className="border-b border-line"><tr>
              <SortTh field="severity_rank" label="Severity" sort={sort} order={order} onSort={onSort} />
              <SortTh field="account_id" label="Account" sort={sort} order={order} onSort={onSort} />
              <SortTh field="risk_score" label="Risk index" sort={sort} order={order} onSort={onSort} />
              <Th>Reasons</Th><SortTh field="last_activity_at" label="Last activity" sort={sort} order={order} onSort={onSort} />
              <SortTh field="status" label="Status" sort={sort} order={order} onSort={onSort} /></tr></thead>
            <tbody className="divide-y divide-line">{rows.map((a) => (
              <tr key={a.alert_id} tabIndex={0} onClick={() => nav(`/alerts/${a.alert_id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/alerts/${a.alert_id}`)} className="cursor-pointer hover:bg-s3/60 focus-visible:bg-s3/60">
                <td className="px-3 py-2.5"><SeverityBadge severity={a.severity} /></td>
                <td className="px-3 py-2.5"><AccountLink id={a.account_id} /><div className="font-mono text-2xs text-fg-3">{a.alert_id}</div></td>
                <td className="px-3 py-2.5"><RiskBar value={a.risk_score} severity={a.severity} /></td>
                <td className="px-3 py-2.5"><div className="flex max-w-xs flex-wrap gap-1">{a.reason_codes.map((c) => <RuleBadge key={c} code={c} />)}</div></td>
                <td className="num px-3 py-2.5 text-fg-2">{dt(a.last_activity_at)}</td>
                <td className="px-3 py-2.5"><StatusBadge status={a.status} resolution={a.resolution} />{a.notes_count > 0 && <span className="ml-2 text-2xs text-fg-3">{a.notes_count} note{a.notes_count > 1 ? "s" : ""}</span>}</td></tr>))}</tbody></table></div>)}
        <Pagination meta={query.data?.meta} onPage={setPage} label="alerts" />
      </Card>
    </>
  );
}
