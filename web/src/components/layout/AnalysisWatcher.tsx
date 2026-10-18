import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAnalysisStatus } from "@/api/hooks";
import { useToast } from "@/components/ui/Toast";

/** Refreshes every data query when a run finishes, and reports the outcome. */
export function AnalysisWatcher() {
  const { data } = useAnalysisStatus();
  const qc = useQueryClient();
  const { toast } = useToast();
  const prev = useRef<string | undefined>(undefined);
  useEffect(() => {
    const s = data?.status;
    if (prev.current === "running" && s === "completed") {
      void qc.invalidateQueries();
      toast("success", "Analysis completed. All views refreshed.");
    } else if (prev.current === "running" && s === "failed") {
      void qc.invalidateQueries({ queryKey: ["ingest"] });
      toast("error", `Analysis failed: ${data?.error ?? "unknown error"}`);
    }
    prev.current = s;
  }, [data?.status, data?.error, qc, toast]);
  return null;
}
