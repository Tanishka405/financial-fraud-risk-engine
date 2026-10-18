import type { CaseStatus, Severity } from "@/api/types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];
export const SEVERITY: Record<Severity, { label: string; text: string; bg: string; ring: string; hex: string; bar: string }> = {
  critical: { label: "Critical", text: "text-crit", bg: "bg-crit/12", ring: "ring-crit/30", hex: "#ef4444", bar: "bg-crit" },
  high: { label: "High", text: "text-red", bg: "bg-red/10", ring: "ring-red/25", hex: "#f87171", bar: "bg-red" },
  medium: { label: "Medium", text: "text-amber", bg: "bg-amber/10", ring: "ring-amber/25", hex: "#fbbf24", bar: "bg-amber" },
  low: { label: "Low", text: "text-cyan", bg: "bg-cyan/10", ring: "ring-cyan/25", hex: "#22d3ee", bar: "bg-cyan" },
};
export const NEUTRAL_NODE = "#4a5a78";

export const STATUS: Record<CaseStatus, { label: string; text: string; bg: string; dot: string }> = {
  open: { label: "Open", text: "text-fg-2", bg: "bg-s4", dot: "bg-fg-3" },
  under_review: { label: "Under review", text: "text-cyan", bg: "bg-cyan/10", dot: "bg-cyan" },
  closed: { label: "Closed", text: "text-emerald", bg: "bg-emerald/10", dot: "bg-emerald" },
};
export const RESOLUTION_LABEL: Record<string, string> = {
  reviewed_no_action: "Reviewed — no action",
  reviewed_escalate: "Reviewed — escalate for further review",
  data_quality_issue: "Data-quality issue",
};

/** Plain-language help for technical metrics (shown as tooltips). */
export const HELP = {
  risk_score: "Ordinal risk index (0–100) for prioritising human review. Uncalibrated: it is NOT a probability of fraud.",
  rule_score: "Saturating combination of the weights of matched AML-style rules: 100 × (1 − ∏(1 − w)).",
  model_score: "Isolation Forest percentile within this dataset. 98 means more unusual than 98% of accounts here. Relative, not a probability.",
  inflow_outflow: "Total received ÷ total sent. Shown as ‘pure sink’ when the account never sends funds.",
  max_daily: "Largest number of transactions (sent or received) the account was involved in on any single day.",
  counterparties: "Distinct accounts this account exchanged funds with, in either direction.",
  degree: "Number of individual transactions touching the account (repeats are counted, not collapsed).",
  robust_z: "Descriptive distance from the typical account, in median-absolute-deviation units. Not a model attribution.",
} as const;
