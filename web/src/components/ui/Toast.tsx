import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle, X } from "lucide-react";

type Kind = "success" | "error";
interface T { id: number; kind: Kind; text: string }
const Ctx = createContext<{ toast: (kind: Kind, text: string) => void }>({ toast: () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const toast = useCallback((kind: Kind, text: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  const v = useMemo(() => ({ toast }), [toast]);
  return (
    <Ctx.Provider value={v}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} role={t.kind === "error" ? "alert" : "status"} className="pointer-events-auto flex items-start gap-2.5 rounded-lg border border-line-strong bg-s3 px-3 py-2.5 text-[13px] shadow-2xl animate-slide-in">
            {t.kind === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-red" />}
            <p className="flex-1 text-fg-2">{t.text}</p>
            <button aria-label="Dismiss" className="text-fg-3 hover:text-fg" onClick={() => setItems((s) => s.filter((x) => x.id !== t.id))}><X className="size-3.5" /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
