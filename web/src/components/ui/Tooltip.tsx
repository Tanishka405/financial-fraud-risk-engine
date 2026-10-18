import { useId, type ReactNode } from "react";
import { HelpCircle } from "lucide-react";
import { cn } from "@/lib/cn";

/** Accessible hover/focus tooltip (no portal; fine for short help text). */
export function Tip({ text, children, className }: { text: string; children?: ReactNode; className?: string }) {
  const id = useId();
  return (
    <span className={cn("group relative inline-flex items-center", className)}>
      <span tabIndex={0} aria-describedby={id} className="inline-flex cursor-help items-center gap-1 outline-none">
        {children ?? <HelpCircle className="size-3.5 text-fg-3 group-hover:text-fg-2" aria-label="Help" />}
      </span>
      <span id={id} role="tooltip" className="pointer-events-none invisible absolute left-1/2 top-full z-50 mt-1.5 w-60 -translate-x-1/2 rounded-md border border-line-strong bg-s3 px-2.5 py-2 text-xs font-normal normal-case leading-snug tracking-normal text-fg-2 opacity-0 shadow-xl transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
        {text}
      </span>
    </span>
  );
}
