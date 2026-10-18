import type { ReactNode } from "react";
import { AlertTriangle, Info, SearchX, WifiOff } from "lucide-react";
import { ApiError } from "@/api/client";
import { cn } from "@/lib/cn";
import { Button } from "./Button";

export function EmptyState({ icon, title, body, action, className }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in", className)}>
      <div className="mb-3 grid size-10 place-items-center rounded-full border border-line-strong bg-s3 text-fg-3">{icon ?? <SearchX className="size-5" />}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      {body && <p className="mt-1 max-w-md text-[13px] text-fg-3">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const e = error instanceof ApiError ? error : null;
  const network = e?.code === "NETWORK_ERROR";
  const title = network ? "Backend unreachable" : e?.code === "INVALID_FILTER" || e?.code === "VALIDATION_ERROR" || e?.code === "INVALID_SORT" ? "Invalid filter" : "Something went wrong";
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <div className="mb-3 grid size-10 place-items-center rounded-full border border-red/30 bg-red/10 text-red">{network ? <WifiOff className="size-5" /> : <AlertTriangle className="size-5" />}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      <p className="mt-1 max-w-md text-[13px] text-fg-2">{e?.message ?? (error instanceof Error ? error.message : "Unknown error")}</p>
      {e?.code && <p className="mt-1 font-mono text-2xs text-fg-3">{e.code}</p>}
      {onRetry && <Button className="mt-4" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Callout({ tone = "info", title, children, className }: { tone?: "info" | "warn" | "danger" | "success"; title?: string; children?: ReactNode; className?: string }) {
  const t = { info: "border-cyan/25 bg-cyan/5 text-cyan", warn: "border-amber/25 bg-amber/5 text-amber", danger: "border-red/30 bg-red/8 text-red", success: "border-emerald/25 bg-emerald/5 text-emerald" }[tone];
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={cn("flex gap-2.5 rounded-lg border px-3 py-2.5 text-[13px]", t, className)}>
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 text-fg-2">{title && <p className="font-medium text-fg">{title}</p>}{children}</div>
    </div>
  );
}
