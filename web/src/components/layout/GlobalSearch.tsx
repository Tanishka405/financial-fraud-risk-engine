import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Search, User, ArrowLeftRight } from "lucide-react";
import { useSearch } from "@/api/hooks";
import { SeverityBadge } from "@/components/domain/badges";
import { inr } from "@/lib/format";

interface Item { key: string; group: string; label: string; sub: string; to: string; severity?: "low" | "medium" | "high" | "critical" }

export function GlobalSearch() {
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);
  const ref = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 200); return () => clearTimeout(t); }, [q]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); ref.current?.focus(); } };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);
  const { data, isFetching } = useSearch(dq);
  const items: Item[] = useMemo(() => {
    if (!data || !dq) return [];
    return [
      ...data.accounts.map((a): Item => ({ key: `a${a.account_id}`, group: "Accounts", label: a.account_id, sub: `Risk ${a.risk_score.toFixed(1)}`, to: `/accounts/${a.account_id}`, severity: a.severity })),
      ...data.alerts.map((a): Item => ({ key: `l${a.alert_id}`, group: "Alerts", label: a.alert_id, sub: `Risk ${a.risk_score.toFixed(1)}`, to: `/alerts/${a.alert_id}`, severity: a.severity })),
      ...data.transactions.map((t): Item => ({ key: `t${t.transaction_id}`, group: "Transactions", label: t.transaction_id, sub: `${t.sender_account_id} → ${t.receiver_account_id} · ${inr(t.amount_inr)}`, to: `/transactions?q=${t.transaction_id}` })),
    ];
  }, [data, dq]);
  const go = (it: Item) => { nav(it.to); setOpen(false); setQ(""); ref.current?.blur(); };
  const icon = { Accounts: <User className="size-3.5" />, Alerts: <Bell className="size-3.5" />, Transactions: <ArrowLeftRight className="size-3.5" /> } as const;
  return (
    <div className="relative min-w-0 flex-1 md:max-w-md">
      <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-fg-3" aria-hidden />
      <input ref={ref} role="combobox" aria-expanded={open && !!dq} aria-controls="gs-list" aria-label="Global search" value={q} placeholder="Search accounts, transactions, alerts…"
        onChange={(e) => { setQ(e.target.value); setIdx(0); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, items.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter" && items[idx]) go(items[idx]);
          else if (e.key === "Escape") { setOpen(false); ref.current?.blur(); }
        }}
        className="h-8 w-full rounded-md border border-line-strong bg-s2 pl-8 pr-12 text-[13px] text-fg placeholder:text-fg-3 focus:border-cyan focus:outline-none focus:ring-1 focus:ring-cyan/40" />
      <kbd className="pointer-events-none absolute right-2 top-1.5 hidden rounded border border-line-strong px-1 font-mono text-[10px] text-fg-3 sm:block">Ctrl K</kbd>
      {open && dq && (
        <ul id="gs-list" role="listbox" className="absolute left-0 right-0 top-10 z-50 max-h-96 overflow-auto rounded-lg border border-line-strong bg-s2 p-1 shadow-2xl animate-fade-in">
          {items.length === 0 && <li className="px-3 py-3 text-xs text-fg-3">{isFetching ? "Searching…" : `No results for “${dq}”.`}</li>}
          {items.map((it, i) => (
            <li key={it.key} role="option" aria-selected={i === idx} onMouseDown={(e) => { e.preventDefault(); go(it); }} onMouseEnter={() => setIdx(i)}
              className={`flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-1.5 ${i === idx ? "bg-s4" : ""}`}>
              <span className="text-fg-3">{icon[it.group as keyof typeof icon]}</span>
              <span className="min-w-0 flex-1"><span className="block truncate font-mono text-xs text-fg">{it.label}</span><span className="block truncate text-2xs text-fg-3">{it.group} · {it.sub}</span></span>
              {it.severity && <SeverityBadge severity={it.severity} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
