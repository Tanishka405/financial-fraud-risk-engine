import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const base = "h-8 w-full rounded-md border border-line-strong bg-s2 px-2.5 text-[13px] text-fg placeholder:text-fg-3 transition-colors hover:border-[#3a4d78] focus:border-cyan focus:outline-none focus:ring-1 focus:ring-cyan/40";

/**
 * `group` must be used when the children are a composite control (e.g. Segmented) rather than a single input:
 * a <label> implicitly names only its FIRST labelable descendant, which would mislabel the first option.
 */
export function Field({ label, children, hint, className, group }: { label: string; children: ReactNode; hint?: string; className?: string; group?: boolean }) {
  const id = useId();
  if (group) {
    return (
      <div role="group" aria-labelledby={id} className={cn("flex min-w-0 flex-col gap-1", className)}>
        <span id={id} className="label">{label}</span>
        {children}
        {hint && <span className="text-2xs text-fg-3">{hint}</span>}
      </div>
    );
  }
  return (
    <label className={cn("flex min-w-0 flex-col gap-1", className)}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="text-2xs text-fg-3">{hint}</span>}
    </label>
  );
}
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={cn(base, className)} {...p} />;
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...p }, ref) {
  return <select ref={ref} className={cn(base, "pr-6", className)} {...p}>{children}</select>;
});
export function Segmented<T extends string | number>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line-strong bg-s2 p-0.5">
      {options.map((o) => (
        <button key={String(o.value)} role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cn("h-7 rounded px-2.5 text-xs font-medium transition-colors", o.value === value ? "bg-s4 text-fg shadow-sm" : "text-fg-3 hover:text-fg-2")}>{o.label}</button>
      ))}
    </div>
  );
}
export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-fg-2">
      <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
        className={cn("relative h-4.5 w-8 rounded-full border transition-colors", checked ? "border-emerald/60 bg-emerald/30" : "border-line-strong bg-s3")}>
        <span className={cn("absolute top-0.5 size-3 rounded-full transition-all", checked ? "left-4 bg-emerald" : "left-0.5 bg-fg-3")} />
      </button>
      {label}
    </label>
  );
}
