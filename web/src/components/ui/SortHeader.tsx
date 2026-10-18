import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";

export function SortTh({ field, label, sort, order, onSort, align = "left", className }: {
  field: string; label: string; sort: string; order: "asc" | "desc"; onSort: (f: string) => void; align?: "left" | "right"; className?: string;
}) {
  const active = sort === field;
  return (
    <th scope="col" aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"} className={cn("px-3 py-2 font-semibold", className)}>
      <button onClick={() => onSort(field)} className={cn("label inline-flex items-center gap-1 hover:text-fg-2", align === "right" && "flex-row-reverse", active && "text-fg-2")}>
        {label}
        {active ? (order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />) : <ChevronsUpDown className="size-3 opacity-40" />}
      </button>
    </th>
  );
}
export const Th = ({ children, align = "left", className }: { children?: React.ReactNode; align?: "left" | "right"; className?: string }) => (
  <th scope="col" className={cn("label px-3 py-2", align === "right" && "text-right", className)}>{children}</th>
);
