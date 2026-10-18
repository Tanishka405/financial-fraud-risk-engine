import { ChevronLeft, ChevronRight } from "lucide-react";
import type { PageMeta } from "@/api/types";
import { int } from "@/lib/format";
import { Button } from "./Button";

export function Pagination({ meta, onPage, label = "rows" }: { meta?: PageMeta; onPage: (p: number) => void; label?: string }) {
  if (!meta) return null;
  const from = meta.total === 0 ? 0 : (meta.page - 1) * meta.page_size + 1;
  const to = Math.min(meta.page * meta.page_size, meta.total);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-xs text-fg-3">
      <span className="num">{int(from)}–{int(to)} of {int(meta.total)} {label}</span>
      <div className="flex items-center gap-1.5">
        <Button size="sm" variant="ghost" aria-label="Previous page" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}><ChevronLeft className="size-4" /></Button>
        <span className="num min-w-16 text-center text-fg-2">Page {meta.page} / {meta.total_pages}</span>
        <Button size="sm" variant="ghost" aria-label="Next page" disabled={meta.page >= meta.total_pages} onClick={() => onPage(meta.page + 1)}><ChevronRight className="size-4" /></Button>
      </div>
    </nav>
  );
}
