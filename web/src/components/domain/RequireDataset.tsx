import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Database, Loader2, Sparkles } from "lucide-react";
import { useAnalysisStatus, useDataset, useRunSynthetic } from "@/api/hooks";
import { ErrorState, EmptyState } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

/** First-run gate: every data page renders only once a dataset exists. */
export function RequireDataset({ children }: { children: ReactNode }) {
  const ds = useDataset();
  const st = useAnalysisStatus();
  const run = useRunSynthetic();
  const { toast } = useToast();
  if (ds.isError) return <ErrorState error={ds.error} onRetry={() => void ds.refetch()} />;
  if (ds.isLoading) return <div className="space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></div>;
  if (ds.data?.loaded) return <>{children}</>;
  const running = st.data?.status === "running" || run.isPending;
  return (
    <EmptyState className="min-h-[60vh]" icon={running ? <Loader2 className="size-5 animate-spin" /> : <Database className="size-5" />}
      title={running ? "Analysis in progress" : "No dataset loaded yet"}
      body={running ? st.data?.stage : st.data?.status === "failed" ? `The last run failed: ${st.data.error}` : "Generate the deterministic synthetic dataset, or upload your own transaction CSV, to start exploring."}
      action={!running && (
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => run.mutate({}, { onError: (e) => toast("error", e.message) })}><Sparkles className="size-4" />Generate synthetic dataset</Button>
          <Link to="/data"><Button>Upload CSV</Button></Link>
        </div>)} />
  );
}
