import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Badge({ children, className, tone = "neutral" }: { children: ReactNode; className?: string; tone?: "neutral" | "emerald" | "cyan" | "amber" | "red" }) {
  const t = { neutral: "bg-s4 text-fg-2", emerald: "bg-emerald/10 text-emerald", cyan: "bg-cyan/10 text-cyan", amber: "bg-amber/10 text-amber", red: "bg-red/10 text-red" }[tone];
  return <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-2xs font-medium", t, className)}>{children}</span>;
}
