import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeftRight, FilterX } from "lucide-react";
import { useTransactions } from "@/api/hooks";
import type { TxFilters } from "@/api/types";
import { AccountLink, RiskBar, RuleBadge, TxnLink, typeLabel } from "@/components/domain/badges";
import { TransactionDrawer } from "@/components/domain/TransactionDrawer";
import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { Field, Input, Select, Toggle } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { SortTh, Th } from "@/components/ui/SortHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useDebounced } from "@/lib/useDebounced";
import { dayToIso, dt, inr } from "@/lib/format";

const TYPES = ["UPI", "NEFT", "IMPS", "RTGS", "CASH_DEPOSIT", "CASH_WITHDRAWAL"];

export default function Transactions() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [account, setAccount] = useState(sp.get("account") ?? "");
  const [type, setType] = useState(""); const [minA, setMinA] = useState(""); const [maxA, setMaxA] = useState("");
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [flagged, setFlagged] = useState(false);
  const [sort, setSort] = useState("timestamp"); const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1); const [pageSize, setPageSize] = useState(25);
  const [open, setOpen] = useState<string | null>(null);
  const dq = useDebounced(q), dacc = useDebounced(account), dmin = useDebounced(minA), dmax = useDebounced(maxA);

  const f: TxFilters = useMemo(() => ({ page, page_size: pageSize, q: dq.trim() || undefined, account: dacc.trim() || undefined, transaction_type: type || undefined,
    min_amount: dmin || undefined, max_amount: dmax || undefined, from: dayToIso(from), to: dayToIso(to, true), flagged: flagged || undefined, sort, order }),
    [page, pageSize, dq, dacc, type, dmin, dmax, from, to, flagged, sort, order]);
  const query = useTransactions(f);
  const active = !!(q || account || type || minA || maxA || from || to || flagged);
  const reset = () => { setQ(""); setAccount(""); setType(""); setMinA(""); setMaxA(""); setFrom(""); setTo(""); setFlagged(false); setPage(1); setSp({}); };
  const upd = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(1); };
  const onSort = (field: string) => { if (field === sort) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(field); setOrder("desc"); } setPage(1); };
  const rows = query.data?.items ?? [];
  return (
    <>
      <PageHeader title="Transaction Explorer" subtitle="Every validated transaction in the loaded dataset. Risk columns show the sender’s and receiver’s account-level risk index, not a per-transaction verdict." />
      <Card>
        <div className="grid grid-cols-2 gap-3 border-b border-line p-4 md:grid-cols-4 xl:grid-cols-8">
          <Field label="Search" className="col-span-2"><Input aria-label="Search transactions" placeholder="Txn ID or account…" value={q} onChange={(e) => upd(setQ)(e.target.value)} /></Field>
          <Field label="Account"><Input aria-label="Filter by account" placeholder="ACC00005" value={account} onChange={(e) => upd(setAccount)(e.target.value)} /></Field>
          <Field label="Type"><Select aria-label="Transaction type" value={type} onChange={(e) => upd(setType)(e.target.value)}><option value="">All types</option>{TYPES.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}</Select></Field>
          <Field label="Min ₹"><Input type="number" min={0} inputMode="decimal" aria-label="Minimum amount" value={minA} onChange={(e) => upd(setMinA)(e.target.value)} /></Field>
          <Field label="Max ₹"><Input type="number" min={0} inputMode="decimal" aria-label="Maximum amount" value={maxA} onChange={(e) => upd(setMaxA)(e.target.value)} /></Field>
          <Field label="From (IST)"><Input type="date" aria-label="From date" value={from} onChange={(e) => upd(setFrom)(e.target.value)} /></Field>
          <Field label="To (IST)"><Input type="date" aria-label="To date" value={to} onChange={(e) => upd(setTo)(e.target.value)} /></Field>
          <div className="col-span-2 flex items-center gap-4 md:col-span-4 xl:col-span-8">
            <Toggle checked={flagged} onChange={upd(setFlagged)} label="Only transactions cited as rule evidence" />
            <Field label="" className="ml-auto w-32"><Select aria-label="Rows per page" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>{[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}</Select></Field>
            <Button variant="ghost" size="sm" onClick={reset} disabled={!active}><FilterX className="size-3.5" />Clear filters</Button>
          </div>
        </div>
        {query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.isLoading ? <TableSkeleton cols={6} /> : rows.length === 0 ? (
          <EmptyState icon={<ArrowLeftRight className="size-5" />} title="No transactions match" body="Try widening the amount range or date window, or clear the filters." action={<Button onClick={reset}>Clear filters</Button>} />
        ) : (
          <div className={`overflow-x-auto transition-opacity ${query.isFetching ? "opacity-60" : ""}`}>
            <table className="w-full min-w-[860px] text-[13px]">
              <thead className="border-b border-line"><tr>
                <SortTh field="transaction_id" label="Transaction" sort={sort} order={order} onSort={onSort} />
                <SortTh field="sender_account_id" label="Sender" sort={sort} order={order} onSort={onSort} />
                <SortTh field="receiver_account_id" label="Receiver" sort={sort} order={order} onSort={onSort} />
                <SortTh field="amount_inr" label="Amount" align="right" sort={sort} order={order} onSort={onSort} className="text-right" />
                <SortTh field="timestamp" label="Time (IST)" sort={sort} order={order} onSort={onSort} />
                <SortTh field="transaction_type" label="Type" sort={sort} order={order} onSort={onSort} />
                <SortTh field="sender_risk" label="Sender risk" sort={sort} order={order} onSort={onSort} />
                <Th>Rules</Th></tr></thead>
              <tbody className="divide-y divide-line">{rows.map((t) => (
                <tr key={t.transaction_id} tabIndex={0} onClick={() => setOpen(t.transaction_id)} onKeyDown={(e) => e.key === "Enter" && setOpen(t.transaction_id)} className="cursor-pointer hover:bg-s3/60 focus-visible:bg-s3/60">
                  <td className="px-3 py-2"><TxnLink id={t.transaction_id} onOpen={setOpen} /></td>
                  <td className="px-3 py-2"><AccountLink id={t.sender_account_id} /></td><td className="px-3 py-2"><AccountLink id={t.receiver_account_id} /></td>
                  <td className="num px-3 py-2 text-right text-fg">{inr(t.amount_inr)}</td><td className="num px-3 py-2 text-fg-2">{dt(t.timestamp)}</td>
                  <td className="px-3 py-2 text-fg-2">{typeLabel(t.transaction_type)}</td><td className="px-3 py-2"><RiskBar value={t.sender_risk} /></td>
                  <td className="px-3 py-2"><div className="flex gap-1">{t.flagged_rules.slice(0, 2).map((c) => <RuleBadge key={c} code={c} />)}{t.flagged_rules.length > 2 && <span className="text-2xs text-fg-3">+{t.flagged_rules.length - 2}</span>}</div></td>
                </tr>))}</tbody>
            </table>
          </div>)}
        <Pagination meta={query.data?.meta} onPage={setPage} label="transactions" />
      </Card>
      {open && <TransactionDrawer id={open} onClose={() => setOpen(null)} onOpen={setOpen} />}
    </>
  );
}
