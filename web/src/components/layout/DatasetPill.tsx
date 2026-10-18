import { Link } from "react-router-dom";
import { Database, Loader2 } from "lucide-react";
import { useAnalysisStatus, useDataset } from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { dt } from "@/lib/format";

export function DatasetPill() {
  const { data: d } = useDataset();
  const { data: st } = useAnalysisStatus();
  const running = st?.status === "running";
  return (
    <Link to="/data" className="group flex shrink-0 items-center gap-2 rounded-md border border-line-strong bg-s2 px-2.5 py-1 hover:border-[#3a4d78]" title="Open Data & Pipeline">
      {running ? <Loader2 className="size-3.5 animate-spin text-cyan" /> : <Database className="size-3.5 text-fg-3" />}
      <div className="hidden min-w-0 max-w-[16rem] leading-tight sm:block">
        <div className="truncate text-xs font-medium text-fg">{running ? st?.stage || "Analysing…" : d?.loaded ? d.name : "No dataset loaded"}</div>
        <div className="truncate text-2xs text-fg-3">{d?.loaded ? `Analysed ${dt(d.analysis_completed_at)}` : running ? "Analysis in progress" : "Generate or upload data"}</div>
      </div>
      {d?.loaded && d.is_synthetic && <Badge tone="amber">Synthetic</Badge>}
    </Link>
  );
}
