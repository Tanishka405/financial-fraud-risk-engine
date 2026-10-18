import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
const V: Record<Variant, string> = {
  primary: "bg-emerald text-ink hover:bg-emerald/90 font-semibold",
  secondary: "bg-s3 text-fg border border-line-strong hover:bg-s4",
  ghost: "text-fg-2 hover:bg-s3 hover:text-fg",
  danger: "bg-crit/15 text-red border border-crit/30 hover:bg-crit/25",
};
interface Props extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: Variant; size?: "sm" | "md"; loading?: boolean }

export const Button = forwardRef<HTMLButtonElement, Props>(function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]", V[variant], className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});
