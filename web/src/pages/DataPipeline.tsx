import { useRef, useState } from "react";
import { CheckCircle2, Download, FileUp, Loader2, Sparkles, XCircle } from "lucide-react";
import { useAnalysisStatus, useDataset, useDetectionConfig, useEvaluation, useIngest, useRejects, useRunSynthetic, useUpload } from "@/api/hooks";
import { MAX_UPLOAD_BYTES, API_BASE } from "@/api/config";
import { ApiError } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, PageHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field, Input, Toggle } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { Callout } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { dt, int, pct } from "@/lib/format";

const TEMPLATE = "transaction_id,sender_account_id,receiver_account_id,amount_inr,timestamp,transaction_type\nTXN0001,ACC001,ACC002,2500.00,2024-03-01 10:15:00,UPI\n";

export default function DataPipeline() {
  const ds = useDataset(); const st = useAnalysisStatus(); const ing = useIngest(); const cfg = useDetectionConfig();
  const run = useRunSynthetic(); const up = useUpload(); const { toast } = useToast();
  const loaded = !!ds.data?.loaded; const d = ds.data;
  const ev = useEvaluation(loaded && !!d?.is_synthetic);
  const [rp, setRp] = useState(1); const rejects = useRejects(rp);
  const [seed, setSeed] = useState("42"); const [accounts, setAccounts] = useState("200"); const [normal, setNormal] = useState("3000");
  const [structuring, setStructuring] = useState(false);
  const [confirm, setConfirm] = useState<null | "run">(null);
  const [file, setFile] = useState<File | null>(null); const [fileErr, setFileErr] = useState<string | null>(null); const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const running = st.data?.status === "running";

  const numErr = (v: string, lo: number, hi: number) => (v === "" || !Number.isInteger(Number(v)) || Number(v) < lo || Number(v) > hi ? `Integer ${lo}–${hi}` : null);
  const errs = { seed: numErr(seed, 0, 2147483647), accounts: numErr(accounts, structuring ? 30 : 20, 2000), normal: numErr(normal, 0, 50000) };
  const bad = Object.values(errs).some(Boolean);

  const doRun = () => {
    setConfirm(null);
    run.mutate({ seed: Number(seed), num_accounts: Number(accounts), num_normal_transactions: Number(normal), include_structuring: structuring }, { onSuccess: () => toast("success", "Synthetic analysis started."), onError: (e) => toast("error", e.message) });
  };
  const pick = (f: File | undefined) => {
    setFileErr(null); setFile(null);
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) return setFileErr("Please choose a .csv file.");
    if (f.size === 0) return setFileErr("The file is empty.");
    if (f.size > MAX_UPLOAD_BYTES) return setFileErr(`File is ${(f.size / 1048576).toFixed(1)} MB; the limit is ${MAX_UPLOAD_BYTES / 1048576} MB.`);
    setFile(f);
  };
  const doUpload = () => { if (!file) return; up.mutate(file, { onSuccess: (r) => { toast("success", `Accepted ${int(r.accepted)} rows, rejected ${int(r.rejected)}. Analysis started.`); setFile(null); }, onError: (e) => toast("error", e instanceof ApiError ? `${e.code}: ${e.message}` : e.message) }); };
  const template = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv" })); a.download = "transactions_template.csv"; a.click(); URL.revokeObjectURL(a.href); };
  const uerr = up.error instanceof ApiError ? up.error : null;
  const reasons = Object.entries(ing.data?.reason_counts ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <PageHeader title="Data & Pipeline" subtitle="Load data through the same validation path used by the analytical core. Invalid records are never silently dropped — each is reported with machine-readable reasons." />
      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-4 px-4 py-3">
          {running ? <Loader2 className="size-5 animate-spin text-cyan" /> : st.data?.status === "failed" ? <XCircle className="size-5 text-red" /> : st.data?.status === "completed" ? <CheckCircle2 className="size-5 text-emerald" /> : <div className="size-5 rounded-full border border-line-strong" />}
          <div><div className="text-sm font-medium">{running ? "Analysis in progress" : st.data?.status === "failed" ? "Analysis failed" : st.data?.status === "completed" ? "Analysis completed" : "Idle — no analysis run yet"}</div>
            <div className="text-xs text-fg-3">{running ? st.data?.stage : st.data?.status === "failed" ? st.data.error : st.data?.finished_at ? `Finished ${dt(st.data.finished_at)}` : "Generate or upload data to begin."}</div></div>
          {loaded && <div className="ml-auto flex items-center gap-2 text-xs text-fg-3">{d?.is_synthetic ? <Badge tone="amber">Synthetic data</Badge> : <Badge tone="emerald">Uploaded CSV</Badge>}<span>{d?.name}</span></div>}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Deterministic synthetic dataset" subtitle="Same seed → identical data. Contains injected test scenarios, not real fraud." />
          <div className="space-y-3 px-4 pb-4">
            <div className="grid grid-cols-3 gap-3">
              <Field label="Seed" hint={errs.seed ?? undefined}><Input inputMode="numeric" aria-label="Random seed" aria-invalid={!!errs.seed} value={seed} onChange={(e) => setSeed(e.target.value)} /></Field>
              <Field label="Accounts" hint={errs.accounts ?? undefined}><Input inputMode="numeric" aria-label="Number of accounts" aria-invalid={!!errs.accounts} value={accounts} onChange={(e) => setAccounts(e.target.value)} /></Field>
              <Field label="Normal txns" hint={errs.normal ?? undefined}><Input inputMode="numeric" aria-label="Number of normal transactions" aria-invalid={!!errs.normal} value={normal} onChange={(e) => setNormal(e.target.value)} /></Field>
            </div>
            <Toggle checked={structuring} onChange={setStructuring} label="Include opt-in STRUCTURING scenario (adds 6 cash deposits just below INR 50,000)" />
            <Button variant="primary" disabled={bad || running} loading={run.isPending} onClick={() => (loaded ? setConfirm("run") : doRun())}><Sparkles className="size-4" />Generate &amp; analyse</Button>
          </div></Card>

        <Card><CardHeader title="Upload transaction CSV" subtitle={`Required columns: transaction_id, sender_account_id, receiver_account_id, amount_inr, timestamp, transaction_type · max ${MAX_UPLOAD_BYTES / 1048576} MB / 50,000 rows`} />
          <div className="space-y-3 px-4 pb-4">
            <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
              className={`flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition-colors ${drag ? "border-cyan bg-cyan/5" : "border-line-strong"}`}>
              <FileUp className="size-5 text-fg-3" aria-hidden />
              <p className="text-[13px] text-fg-2">{file ? <><b className="text-fg">{file.name}</b> · {(file.size / 1024).toFixed(1)} KB</> : "Drop a .csv here, or"}</p>
              <input ref={inputRef} type="file" accept=".csv,text/csv" aria-label="Choose CSV file" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
              <Button size="sm" onClick={() => inputRef.current?.click()}>Choose file</Button>
            </div>
            {fileErr && <p role="alert" className="text-xs text-red">{fileErr}</p>}
            {uerr && <Callout tone="danger" title={uerr.code}>{uerr.message}{uerr.code === "MISSING_COLUMNS" && ing.data?.available === false && " Use the template for the expected header."}</Callout>}
            <div className="flex gap-2"><Button variant="primary" disabled={!file || running} loading={up.isPending} onClick={doUpload}>Validate &amp; analyse</Button><Button variant="ghost" onClick={template}><Download className="size-4" />CSV template</Button></div>
            <p className="text-2xs text-fg-3">Timestamps without a timezone are interpreted as IST. Extra columns (including any label-like columns) are ignored and never used as features.</p>
          </div></Card>
      </div>

      <Card className="mt-4"><CardHeader title="Last ingestion" subtitle="Validation outcome — accepted vs rejected" right={ing.data?.rejected ? <a href={`${API_BASE}/api/analysis/rejects.csv`} download><Button size="sm"><Download className="size-3.5" />Download rejects report</Button></a> : undefined} />
        {ing.isLoading ? <Skeleton className="m-4 h-24" /> : !ing.data?.available ? <p className="px-4 pb-4 text-[13px] text-fg-3">Nothing ingested yet.</p> : (
          <div className="px-4 pb-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              {[["Source", ing.data.name], ["Accepted", int(ing.data.accepted)], ["Rejected", int(ing.data.rejected)]].map(([k, v]) => (<div key={k} className="rounded-lg border border-line bg-s2/60 py-2.5"><div className="label">{k}</div><div className={`num mt-1 truncate px-2 text-lg font-semibold ${k === "Rejected" && ing.data?.rejected ? "text-amber" : ""}`}>{v}</div></div>))}
            </div>
            {(ing.data.ignored_columns?.length ?? 0) > 0 && <Callout tone="info" className="mt-3" title="Ignored columns">{ing.data.ignored_columns?.join(", ")} — not part of the canonical schema; never passed to features or models.</Callout>}
            {ing.data.rejected === 0 ? <p className="mt-3 text-[13px] text-emerald">All records passed validation.</p> : (<>
              <h4 className="label mb-2 mt-4">Rejection reasons</h4>
              <div className="flex flex-wrap gap-2">{reasons.map(([r, n]) => <span key={r} className="rounded border border-line-strong bg-s3 px-2 py-1 font-mono text-xs">{r} <b className="num text-amber">{int(n)}</b></span>)}</div>
              <div className="mt-4 overflow-x-auto rounded-lg border border-line"><table className="w-full min-w-[600px] text-xs"><thead className="border-b border-line text-left"><tr><th className="label px-3 py-2">Row</th><th className="label px-3 py-2">Transaction ID</th><th className="label px-3 py-2">Reason codes</th><th className="label px-3 py-2">Details</th></tr></thead>
                <tbody className="divide-y divide-line">{rejects.data?.items.map((r) => (<tr key={r.row_index}><td className="num px-3 py-1.5 text-fg-3">{r.row_index + 2}</td><td className="px-3 py-1.5 font-mono">{r.transaction_id ?? "—"}</td><td className="px-3 py-1.5"><div className="flex flex-wrap gap-1">{r.reasons.map((x) => <span key={x} className="rounded bg-amber/10 px-1.5 py-0.5 font-mono text-[10px] text-amber">{x}</span>)}</div></td><td className="px-3 py-1.5 text-fg-3">{r.details.join("; ")}</td></tr>))}</tbody></table>
                <Pagination meta={rejects.data?.meta} onPage={setRp} label="rejects" /></div>
              <p className="mt-1.5 text-2xs text-fg-3">Row numbers match the CSV file (header = row 1).</p></>)}
          </div>)}</Card>

      {loaded && (<Card className="mt-4"><CardHeader title="Loaded dataset" />
        <dl className="grid gap-x-6 gap-y-2 px-4 pb-4 text-[13px] sm:grid-cols-2 lg:grid-cols-4">{[["Name", d?.name], ["Dataset ID", d?.dataset_id], ["Loaded", dt(d?.loaded_at)], ["Analysed", dt(d?.analysis_completed_at)], ["Window start", dt(d?.window_start)], ["Window end", dt(d?.window_end)], ["Accepted / rejected", `${int(d?.accepted)} / ${int(d?.rejected)}`], ["Isolation Forest", d?.model_ran ? "ran" : "not run"]].map(([k, v]) => (<div key={k}><dt className="text-fg-3">{k}</dt><dd className="num truncate text-fg-2">{v}</dd></div>))}</dl>
        {d?.notes.map((n) => <p key={n} className="mx-4 mb-4 rounded border border-amber/25 bg-amber/5 px-2.5 py-1.5 text-xs text-fg-2">{n}</p>)}</Card>)}

      {loaded && d?.is_synthetic && ev.data?.available && (
        <Card className="mt-4"><CardHeader title="Controlled evaluation on injected scenarios" subtitle="Synthetic labels are used here only — never as features" />
          <div className="px-4 pb-4"><Callout tone="warn" title="Not a real-world accuracy claim">{ev.data.caveat}</Callout>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">{[["Injected accounts", int(ev.data.injected_accounts)], ["Alerted", int(ev.data.alerted_accounts)], ["Injected & alerted", int(ev.data.injected_and_alerted)], ["Recall on injected", pct(ev.data.recall_on_injected)]].map(([k, v]) => (<div key={k} className="rounded-lg border border-line bg-s2/60 p-3"><div className="label">{k}</div><div className="num mt-1 text-lg font-semibold">{v}</div></div>))}</div>
            <table className="mt-3 w-full text-xs"><tbody className="divide-y divide-line">{ev.data.per_scenario_role?.map((r) => (<tr key={r.scenario_role}><td className="py-1.5 font-mono text-fg-2">{r.scenario_role}</td><td className="num py-1.5 text-right text-fg-3">{r.alerted} / {r.accounts} alerted</td></tr>))}</tbody></table></div></Card>)}

      <Card className="mt-4"><CardHeader title="Detection configuration" subtitle="All thresholds are configurable in core/detection/config.py — none are hard-coded in rule logic" />
        <div className="px-4 pb-4">
          <p className="mb-3 text-xs text-fg-3">{cfg.data?.score_formula}</p>
          <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-[13px]"><thead className="text-left"><tr><th className="label py-1.5">Rule</th><th className="label py-1.5">What it detects</th><th className="label py-1.5 text-right">Weight</th></tr></thead>
            <tbody className="divide-y divide-line">{cfg.data?.rules.map((r) => (<tr key={r.code}><td className="py-1.5 pr-3 font-mono text-xs">{r.code}</td><td className="py-1.5 pr-3 text-fg-2">{r.description}</td><td className="num py-1.5 text-right">{r.weight.toFixed(2)}</td></tr>))}</tbody></table></div>
          <details className="mt-3 text-xs"><summary className="cursor-pointer text-fg-2 hover:text-fg">Show all thresholds</summary>
            <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(cfg.data?.thresholds ?? {}).map(([k, v]) => (<div key={k} className="flex justify-between gap-2"><dt className="truncate font-mono text-fg-3">{k}</dt><dd className="num text-fg-2">{String(v)}</dd></div>))}</dl></details>
        </div></Card>

      <ConfirmDialog open={confirm === "run"} title="Replace the loaded dataset?" confirmLabel="Generate & analyse" onCancel={() => setConfirm(null)} onConfirm={doRun}>
        Generating a new synthetic dataset replaces “{d?.name}” and its analysis. Saved case notes stay attached to their original dataset and reappear if you regenerate identical data.</ConfirmDialog>
    </>
  );
}
