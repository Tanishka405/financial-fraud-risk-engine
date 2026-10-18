import { lazy, Suspense, type ReactElement } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { RequireDataset } from "./components/domain/RequireDataset";
import { EmptyState } from "./components/ui/States";
const Overview = lazy(() => import("./pages/Overview"));
const Transactions = lazy(() => import("./pages/Transactions"));
const NetworkPage = lazy(() => import("./pages/Network"));
const Alerts = lazy(() => import("./pages/Alerts"));
const AlertDetailPage = lazy(() => import("./pages/AlertDetail"));
const Accounts = lazy(() => import("./pages/Accounts"));
const AccountDetailPage = lazy(() => import("./pages/AccountDetail"));
const DataPipeline = lazy(() => import("./pages/DataPipeline"));

const fallback = <div className="skeleton h-40 w-full" role="status" aria-label="Loading page" />;
const gated = (el: ReactElement) => <RequireDataset><Suspense fallback={fallback}>{el}</Suspense></RequireDataset>;

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={gated(<Overview />)} />
        <Route path="transactions" element={gated(<Transactions />)} />
        <Route path="network" element={gated(<NetworkPage />)} />
        <Route path="alerts" element={gated(<Alerts />)} />
        <Route path="alerts/:alertId" element={gated(<AlertDetailPage />)} />
        <Route path="accounts" element={gated(<Accounts />)} />
        <Route path="accounts/:accountId" element={gated(<AccountDetailPage />)} />
        <Route path="data" element={<Suspense fallback={fallback}><DataPipeline /></Suspense>} />
        <Route path="*" element={<EmptyState title="Page not found" body="That route does not exist." />} />
      </Route>
    </Routes>
  );
}
