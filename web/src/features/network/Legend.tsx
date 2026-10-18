import { SEVERITY, SEVERITY_ORDER, NEUTRAL_NODE } from "@/lib/tokens";

export function Legend({ mode }: { mode: "aggregated" | "transactions" }) {
  return (
    <div className="max-w-[17rem] rounded-lg border border-line-strong bg-s2/95 p-3 text-[11px] leading-snug text-fg-2 shadow-xl backdrop-blur" aria-label="Legend">
      <p className="label mb-1.5">Legend</p>
      <ul className="space-y-1">
        {SEVERITY_ORDER.slice().reverse().map((s) => (<li key={s} className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: SEVERITY[s].hex }} />{SEVERITY[s].label} severity alert</li>))}
        <li className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: NEUTRAL_NODE }} />Account with no alert</li>
      </ul>
      <div className="my-2 h-px bg-line" />
      <p><b className="text-fg">Node size</b> grows with the number of transactions touching the account.</p>
      <p className="mt-1"><b className="text-fg">Edge thickness</b> grows with INR value; arrows point from sender to receiver.</p>
      <p className="mt-1"><span className="inline-block h-0.5 w-4 translate-y-[-2px] bg-amber" /> <b className="text-fg">Amber edge</b> carries a transaction cited as rule evidence.</p>
      <p className="mt-1"><b className="text-fg">Colour</b> reflects the ordinal risk index of alerted accounts, not proven fraud.</p>
      <p className="mt-1 text-fg-3">{mode === "aggregated" ? "Aggregated: one edge per sender→receiver pair, labelled ×count · total." : "Individual: every transaction is its own edge; repeats are drawn as parallel curves."}</p>
    </div>
  );
}
