import { useState } from "react";
import { Link } from "react-router-dom";
import { Users } from "lucide-react";
import { useAccounts } from "@/api/hooks";
import { AccountLink, RiskBar, SeverityBadge } from "@/components/domain/badges";
import { Card, PageHeader } from "@/components/ui/Card";
import { Field, Input, Select, Toggle } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { SortTh, Th } from "@/components/ui/SortHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useDebounced } from "@/lib/useDebounced";
import { inrCompact, int } from "@/lib/format";

export default function Accounts() {
  const [q, setQ] = useState(""); const [severity, setSeverity] = useState(""); const [hasAlert, setHasAlert] = useState(false);
  const [sort, setSort] = useState("risk_score"); const [order, setOrder] = useState<"asc" | "desc">("desc"); const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const query = useAccounts({ page, page_size: 25, q: dq.trim() || undefined, severity: severity || undefined, has_alert: hasAlert || undefined, sort, order });
  const onSort = (f: string) => { if (f === sort) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(f); setOrder("desc"); } setPage(1); };
  const rows = query.data?.items ?? [];
  return (
    <>
      <PageHeader title="Account Intelligence" subtitle="Every account observed in the dataset, ranked by the combined risk index. Open one for facts, computed metrics, rule matches and the model signal." />
      <Card>
        <div className="flex flex-wrap items-end gap-3 border-b border-line p-4">
          <Field label="Search" className="w-56"><Input aria-label="Search accounts" placeholder="Account ID…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
          <Field label="Severity" className="w-36"><Select aria-label="Severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}><option value="">All</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s}</option>)}</Select></Field>
          <div className="pb-1.5"><Toggle checked={hasAlert} onChange={(v) => { setHasAlert(v); setPage(1); }} label="Only accounts with an alert" /></div>
        </div>
        {query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.isLoading ? <TableSkeleton cols={6} /> : rows.length === 0 ? <EmptyState icon={<Users className="size-5" />} title="No accounts match" body="Adjust the search or filters." /> : (
          <div className={`overflow-x-auto ${query.isFetching ? "opacity-60" : ""}`}><table className="w-full min-w-[760px] text-[13px]">
            <thead className="border-b border-line"><tr>
              <SortTh field="account_id" label="Account" sort={sort} order={order} onSort={onSort} />
              <SortTh field="risk_score" label="Risk index" sort={sort} order={order} onSort={onSort} />
              <Th>Severity</Th>
              <SortTh field="txn_count" label="Txns" align="right" className="text-right" sort={sort} order={order} onSort={onSort} />
              <SortTh field="total_amount_inr" label="Total value" align="right" className="text-right" sort={sort} order={order} onSort={onSort} />
              <SortTh field="counterparties" label="Counterparties" align="right" className="text-right" sort={sort} order={order} onSort={onSort} />
              <Th>Alert</Th></tr></thead>
            <tbody className="divide-y divide-line">{rows.map((a) => (
              <tr key={a.account_id} className="hover:bg-s3/60"><td className="px-3 py-2"><AccountLink id={a.account_id} /></td><td className="px-3 py-2"><RiskBar value={a.risk_score} severity={a.alert_id ? a.severity : null} /></td>
                <td className="px-3 py-2">{a.alert_id ? <SeverityBadge severity={a.severity} /> : <span className="text-fg-3">—</span>}</td>
                <td className="num px-3 py-2 text-right text-fg-2">{int(a.txn_count)}</td><td className="num px-3 py-2 text-right text-fg-2">{inrCompact(a.total_amount_inr)}</td><td className="num px-3 py-2 text-right text-fg-2">{int(a.counterparties)}</td>
                <td className="px-3 py-2">{a.alert_id ? <Link className="font-mono text-xs text-cyan hover:underline" to={`/alerts/${a.alert_id}`}>{a.alert_id}</Link> : <span className="text-fg-3">None</span>}</td></tr>))}</tbody></table></div>)}
        <Pagination meta={query.data?.meta} onPage={setPage} label="accounts" />
      </Card>
    </>
  );
}
