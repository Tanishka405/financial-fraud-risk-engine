import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { POLL_MS } from "./config";
import type {
  AccountDetail, AccountRow, AlertDetail, AlertFilters, AlertList, AnalysisStatus, CaseStatus, DatasetInfo, DetectionConfigOut,
  Evaluation, GraphData, GraphParams, Ingest, Paged, RejectRow, Resolution, RunRequest, SearchResult, Summary, TransactionDetail,
  TxFilters, Transaction, UploadResponse,
} from "./types";

type P = Record<string, string | number | boolean | null | undefined>;

export const useDataset = () => useQuery({ queryKey: ["dataset"], queryFn: () => api.get<DatasetInfo>("/api/dataset") });

export const useAnalysisStatus = () =>
  useQuery({
    queryKey: ["analysis-status"],
    queryFn: () => api.get<AnalysisStatus>("/api/analysis/status"),
    refetchInterval: (q) => (q.state.data?.status === "running" ? POLL_MS : false),
  });

export const useSummary = (enabled = true) => useQuery({ queryKey: ["summary"], queryFn: () => api.get<Summary>("/api/dataset/summary"), enabled });

export const useTransactions = (f: TxFilters) =>
  useQuery({ queryKey: ["transactions", f], queryFn: () => api.get<Paged<Transaction>>("/api/transactions", f as unknown as P), placeholderData: keepPreviousData, retry: false });

export const useTransaction = (id?: string) =>
  useQuery({ queryKey: ["transaction", id], queryFn: () => api.get<TransactionDetail>(`/api/transactions/${encodeURIComponent(id!)}`), enabled: !!id, retry: false });

export const useAccounts = (p: P) =>
  useQuery({ queryKey: ["accounts", p], queryFn: () => api.get<Paged<AccountRow>>("/api/accounts", p), placeholderData: keepPreviousData, retry: false });

export const useAccount = (id?: string) =>
  useQuery({ queryKey: ["account", id], queryFn: () => api.get<AccountDetail>(`/api/accounts/${encodeURIComponent(id!)}`), enabled: !!id, retry: false });

export const useGraph = (p: GraphParams, enabled = true) =>
  useQuery({ queryKey: ["graph", p], queryFn: () => api.get<GraphData>("/api/graph", p as unknown as P), placeholderData: keepPreviousData, enabled, retry: false });

export const useAlerts = (f: AlertFilters) =>
  useQuery({ queryKey: ["alerts", f], queryFn: () => api.get<AlertList>("/api/alerts", f as unknown as P), placeholderData: keepPreviousData, retry: false });

export const useAlert = (id?: string) =>
  useQuery({ queryKey: ["alert", id], queryFn: () => api.get<AlertDetail>(`/api/alerts/${encodeURIComponent(id!)}`), enabled: !!id, retry: false });

export const useSearch = (q: string) =>
  useQuery({ queryKey: ["search", q], queryFn: () => api.get<SearchResult>("/api/search", { q }), enabled: q.trim().length > 0, staleTime: 10_000 });

export const useIngest = () => useQuery({ queryKey: ["ingest"], queryFn: () => api.get<Ingest>("/api/analysis/ingest") });
export const useRejects = (page: number) =>
  useQuery({ queryKey: ["rejects", page], queryFn: () => api.get<Paged<RejectRow>>("/api/analysis/rejects", { page, page_size: 10 }), placeholderData: keepPreviousData });
export const useEvaluation = (enabled: boolean) => useQuery({ queryKey: ["evaluation"], queryFn: () => api.get<Evaluation>("/api/analysis/evaluation"), enabled, retry: false });
export const useDetectionConfig = () => useQuery({ queryKey: ["detection-config"], queryFn: () => api.get<DetectionConfigOut>("/api/analysis/config"), staleTime: Infinity });

export function useRunSynthetic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: Partial<RunRequest>) => api.post<AnalysisStatus>("/api/analysis/run", { source: "synthetic", ...b }),
    onSuccess: (s) => { qc.setQueryData(["analysis-status"], s); },
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.upload<UploadResponse>("/api/analysis/upload", file),
    onSuccess: (r) => { qc.setQueryData(["analysis-status"], r.status); },
    onSettled: () => { void qc.invalidateQueries({ queryKey: ["ingest"] }); void qc.invalidateQueries({ queryKey: ["rejects"] }); },
  });
}

export function useSetStatus(alertId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { status: CaseStatus; resolution?: Resolution }) => api.patch(`/api/alerts/${encodeURIComponent(alertId)}/status`, b),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["alert", alertId] }); void qc.invalidateQueries({ queryKey: ["alerts"] }); void qc.invalidateQueries({ queryKey: ["account"] }); },
  });
}

export function useAddNote(alertId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => api.post(`/api/alerts/${encodeURIComponent(alertId)}/notes`, { body }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["alert", alertId] }); void qc.invalidateQueries({ queryKey: ["alerts"] }); },
  });
}
