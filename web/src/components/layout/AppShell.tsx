import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Bell, Database, LayoutDashboard, Menu, Network, ArrowLeftRight, Users, X, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/cn";
import { AnalysisWatcher } from "./AnalysisWatcher";
import { DatasetPill } from "./DatasetPill";
import { GlobalSearch } from "./GlobalSearch";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/network", label: "Network", icon: Network },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/accounts", label: "Accounts", icon: Users },
  { to: "/data", label: "Data & Pipeline", icon: Database },
];

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5 px-2">
      {NAV.map(({ to, label, icon: I, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => cn("group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors", isActive ? "bg-s4 text-fg" : "text-fg-2 hover:bg-s3 hover:text-fg")}>
          {({ isActive }) => (<><I className={cn("size-4", isActive ? "text-emerald" : "text-fg-3 group-hover:text-fg-2")} aria-hidden /><span className="md:max-lg:hidden">{label}</span></>)}
        </NavLink>
      ))}
    </nav>
  );
}
const Brand = () => (
  <div className="flex items-center gap-2.5 px-4 py-4">
    <div className="grid size-7 place-items-center rounded-md border border-emerald/30 bg-emerald/10"><ShieldAlert className="size-4 text-emerald" aria-hidden /></div>
    <div className="leading-tight md:max-lg:hidden"><div className="text-[13px] font-semibold tracking-tight">Graph Risk Intelligence</div><div className="text-2xs text-fg-3">AML anomaly review</div></div>
  </div>
);

export function AppShell() {
  const [drawer, setDrawer] = useState(false);
  const loc = useLocation();
  return (
    <div className="flex h-full bg-ink">
      <AnalysisWatcher />
      <aside className="hidden shrink-0 border-r border-line bg-s1 md:flex md:w-14 md:flex-col lg:w-56">
        <Brand /><Nav />
        <p className="mt-auto px-4 py-3 text-2xs leading-snug text-fg-3 md:max-lg:hidden">Alerts are leads for human review, not findings of fraud.</p>
      </aside>
      {drawer && (
        <div className="fixed inset-0 z-[80] md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/70" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-64 border-r border-line bg-s1 animate-slide-in">
            <div className="flex items-center justify-between pr-3"><Brand /><button aria-label="Close menu" onClick={() => setDrawer(false)}><X className="size-4 text-fg-3" /></button></div>
            <Nav onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-s1/80 px-3 backdrop-blur md:px-5">
          <button className="md:hidden" aria-label="Open menu" onClick={() => setDrawer(true)}><Menu className="size-5 text-fg-2" /></button>
          <GlobalSearch />
          <div className="ml-auto shrink-0"><DatasetPill /></div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto"><div key={loc.pathname} className="mx-auto max-w-[1500px] p-4 md:p-6 animate-fade-in"><Outlet /></div></main>
      </div>
    </div>
  );
}
