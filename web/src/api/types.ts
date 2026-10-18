export type Severity = "low" | "medium" | "high" | "critical";
export type CaseStatus = "open" | "under_review" | "closed";
export type Resolution = "reviewed_no_action" | "reviewed_escalate" | "data_quality_issue";
export type RunState = "idle" | "running" | "completed" | "failed";

export interface PageMeta { page: number; page_size: number; total: number; total_pages: number }
export interface Paged<T> { items: T[]; meta: PageMeta }

export interface Health { status: "ok"; version: string; dataset_loaded: boolean; analysis_status: RunState }
export interface DatasetInfo {
  loaded: boolean; dataset_id?: string | null; name?: string | null; source?: string | null; is_synthetic?: boolean | null;
  loaded_at?: string | null; accepted?: number | null; rejected?: number | null; window_start?: string | null;
  window_end?: string | null; seed?: number | null; ignored_columns: string[]; analysis_completed_at?: string | null;
  model_ran?: boolean | null; notes: string[];
}
export interface AnalysisStatus {
  status: RunState; stage: string; error?: string | null; started_at?: string | null; finished_at?: string | null; dataset_loaded: boolean;
}
export interface RunRequest { source: "synthetic"; seed?: number; num_accounts?: number; num_normal_transactions?: number }

export interface Transaction {
  transaction_id: string; sender_account_id: string; receiver_account_id: string; amount_inr: number; timestamp: string;
  transaction_type: string; sender_risk: number | null; receiver_risk: number | null; flagged_rules: string[];
}
export interface TransactionDetail {
  transaction: Transaction;
  same_pair: { count: number; total_amount_inr: number; others: Transaction[] };
  flagged_rules: string[]; related_alert_ids: string[]; sender_nearby: Transaction[]; note: string;
}
export interface TxFilters {
  page: number; page_size: number; q?: string; account?: string; transaction_type?: string; min_amount?: string; max_amount?: string;
  from?: string; to?: string; flagged?: boolean; sort: string; order: "asc" | "desc";
}

export interface AccountRow {
  account_id: string; txn_count: number; txn_count_sent: number; txn_count_received: number; total_amount_inr: number;
  counterparties: number; rule_score: number; model_score: number | null; risk_score: number; severity: Severity; n_rules: number;
  alert_id: string | null;
}
export interface RuleMatch {
  rule_code: string; description: string; role: string; weight: number; summary: string; transaction_ids: string[];
  metrics: Record<string, unknown>;
}
export interface FeatureDeviation { feature: string; value: number; population_median: number; robust_z: number }
export interface TimelinePoint { t: string; sent_count: number; sent_amount_inr: number; received_count: number; received_amount_inr: number }
export interface Counterparty {
  account_id: string; sent_count: number; sent_amount_inr: number; received_count: number; received_amount_inr: number;
  severity: Severity | null; has_alert: boolean;
}
export interface AccountDetail {
  account_id: string;
  observed: { txn_count_sent: number; txn_count_received: number; total_amount_sent_inr: number; total_amount_received_inr: number; first_seen: string; last_seen: string };
  computed_features: {
    avg_amount_sent_inr: number | null; avg_amount_received_inr: number | null; unique_counterparties_sent: number;
    unique_counterparties_received: number; inflow_outflow_ratio: number | null; inflow_outflow_ratio_note: string | null;
    active_days: number; max_daily_txn_count: number;
  };
  graph_metrics: Record<string, number>;
  scores: { rule_score: number; model_score: number | null; risk_score: number; severity: Severity };
  rule_matches: RuleMatch[];
  model_signal: { model_score: number | null; feature_deviations: FeatureDeviation[]; note: string };
  alert: { alert_id: string; severity: Severity; status: CaseStatus } | null;
  timeline: { bucket: "hour" | "day"; points: TimelinePoint[] };
  top_counterparties: Counterparty[];
  recent_transactions: Transaction[];
}

export interface TopAccount { account_id: string; risk_score: number; severity: Severity; txn_count: number; total_amount_inr: number; alert_id: string | null }
export interface RecentAlert {
  alert_id: string; account_id: string; severity: Severity; risk_score: number; reason_codes: string[]; summary: string;
  last_activity_at: string | null; max_evidence_amount_inr: number | null;
}
export interface Summary {
  kpis: { total_transactions: number; total_accounts: number; total_value_inr: number; suspicious_accounts: number; alerts: number; rejected_records: number };
  severity_distribution: Record<Severity, number>;
  account_severity_distribution: Record<string, number>;
  time_series: { bucket: "hour" | "day"; points: { t: string; count: number; value_inr: number }[] };
  by_type: { transaction_type: string; count: number; value_inr: number }[];
  top_risk_accounts: TopAccount[]; most_active_accounts: TopAccount[]; recent_alerts: RecentAlert[];
  model_ran: boolean; notes: string[];
}

export interface GraphNode {
  id: string; is_center: boolean; risk_score: number | null; severity: Severity | null; has_alert: boolean; reason_codes: string[];
  degree_total: number; counterparties: number; visible_in: number; visible_out: number; visible_in_inr: number; visible_out_inr: number;
}
export interface GraphEdge {
  id: string; source: string; target: string; aggregated: boolean; txn_count: number; total_amount_inr: number;
  min_amount_inr?: number; max_amount_inr?: number; first_at?: string; last_at?: string; transaction_ids: string[];
  flagged: boolean; timestamp?: string; transaction_type?: string;
}
export interface GraphData {
  mode: "aggregated" | "transactions"; center: string | null; depth: number | null; nodes: GraphNode[]; edges: GraphEdge[];
  meta: { node_count: number; edge_count: number; transactions_represented: number; truncated: boolean; scope_nodes: number; limit_nodes: number; max_transaction_edges: number; note: string };
}
export interface GraphParams {
  center?: string; depth?: number; min_amount?: string; from?: string; to?: string; mode?: "aggregated" | "transactions"; limit_nodes?: number; only_flagged?: boolean;
}

export interface CaseEvent { id: number; kind: "status" | "note"; from_status?: string | null; to_status?: CaseStatus | null; resolution?: Resolution | null; body?: string | null; created_at: string }
export interface AlertRow {
  alert_id: string; account_id: string; severity: Severity; severity_rank: number; risk_score: number; rule_score: number;
  model_score: number | null; reason_codes: string[]; summary: string; basis: string; status: CaseStatus; resolution: Resolution | null;
  notes_count: number; updated_at: string | null; last_activity_at: string | null; generated_at: string | null;
}
export interface AlertList extends Paged<AlertRow> { facets: { severity: Record<string, number>; status: Record<string, number>; reason: Record<string, number> } }
export interface AlertFilters { page: number; page_size: number; q?: string; severity?: string; status?: string; reason?: string; account?: string; sort: string; order: "asc" | "desc" }
export interface AlertDetail {
  alert_id: string; account_id: string; severity: Severity; risk_score: number; rule_score: number; model_score: number | null;
  basis: string; reason_codes: string[]; summary: string; generated_at: string | null; last_activity_at: string | null; is_synthetic_data: boolean;
  explanation: {
    disclaimer: string; formula: string;
    rule_score_breakdown: { rule_code: string; weight: number; description: string }[];
    model: { model_score: number | null; meaning: string };
    severity_bands: Record<string, number>;
  };
  rule_matches: RuleMatch[]; feature_deviations: FeatureDeviation[];
  account_features: Record<string, number | null>;
  related_transactions: Transaction[]; related_transactions_total: number;
  network_context: { top_counterparties: { account_id: string; txn_count: number; total_amount_inr: number; severity: Severity | null; has_alert: boolean }[] };
  case: { status: CaseStatus; resolution: Resolution | null; updated_at: string | null; notes: CaseEvent[]; history: CaseEvent[]; allowed_transitions: CaseStatus[]; resolutions: Resolution[] };
}

export interface Ingest { available: boolean; name?: string; source?: string; accepted?: number; rejected?: number; ignored_columns?: string[]; at?: string; reason_counts?: Record<string, number> }
export interface RejectRow { row_index: number; transaction_id: string | null; reasons: string[]; details: string[] }
export interface Evaluation {
  available: boolean; reason?: string; scope?: string; injected_accounts?: number; alerted_accounts?: number; injected_and_alerted?: number;
  recall_on_injected?: number | null; alert_precision_vs_injected?: number | null; caveat?: string;
  per_scenario_role?: { scenario_role: string; accounts: number; alerted: number }[];
}
export interface DetectionConfigOut {
  rules: { code: string; description: string; weight: number }[]; thresholds: Record<string, number | boolean | string>;
  score_disclaimer: string; score_formula: string;
}
export interface SearchResult {
  q: string; accounts: { account_id: string; risk_score: number; severity: Severity }[];
  transactions: { transaction_id: string; sender_account_id: string; receiver_account_id: string; amount_inr: number }[];
  alerts: { alert_id: string; account_id: string; severity: Severity; risk_score: number }[];
}
export interface UploadResponse { accepted: number; rejected: number; ignored_columns: string[]; label_like_ignored: string[]; status: AnalysisStatus }
