import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NetworkPage from "@/pages/Network";
import { mockApi, renderWithProviders } from "./utils";

// jsdom lacks DOMMatrixReadOnly, which React Flow reads for its viewport transform.
class DM { m22 = 1; m41 = 0; m42 = 0; constructor(_t?: string) {} }
(globalThis as unknown as { DOMMatrixReadOnly: unknown }).DOMMatrixReadOnly = DM;

const node = (id: string, o: object = {}) => ({ id, is_center: false, risk_score: 10, severity: "low", has_alert: false, reason_codes: [], community_id: 0, degree_total: 2,
  counterparties: 1, visible_in: 1, visible_out: 1, visible_in_inr: 10, visible_out_inr: 10, ...o });
const edge = (s: string, t: string) => ({ id: `${s}>${t}`, source: s, target: t, aggregated: true, txn_count: 1, total_amount_inr: 100, transaction_ids: ["T1"], flagged: false });
const graph = { mode: "aggregated", center: null, depth: null, nodes: [node("A"), node("B", { community_id: 1 }), node("C", { community_id: 1, has_alert: true, severity: "high" })],
  edges: [edge("A", "B"), edge("B", "C")],
  meta: { node_count: 3, edge_count: 2, transactions_represented: 2, truncated: false, scope_nodes: 3, limit_nodes: 40, max_transaction_edges: 1500, note: "n",
    n_communities: 7, modularity: 0.15, communities_note: "c" } };
const routes = () => ({
  "/api/graph/communities": { available: true, total: 2, modularity: 0.15, items: [], interpretation: "Weak community structure", note: "n" },
  "/api/graph": graph,
  "/api/search": { q: "", accounts: [], transactions: [], alerts: [] },
});
const calls = (f: ReturnType<typeof mockApi>) => f.mock.calls.map((c) => String(c[0])).filter((u) => u.includes("/api/graph?") || u.endsWith("/api/graph"));

const EXPECTED: Record<string, { group: string; radiogroup: string; options: string[] }> = {
  Depth: { group: "Depth", radiogroup: "Graph depth", options: ["1 hop", "2", "3"] },
  Colour: { group: "Colour by", radiogroup: "Colour mode", options: ["Risk", "Community"] },
  Edges: { group: "Edges", radiogroup: "Edge mode", options: ["Aggregated", "Individual"] },
};

describe("Network page: segmented controls are correctly named for assistive technology", () => {
  it("each group, radiogroup and EVERY individual radio has the right accessible name", async () => {
    mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network");
    await screen.findByRole("group", { name: "Colour by" });
    for (const e of Object.values(EXPECTED)) {
      const g = screen.getByRole("group", { name: e.group });
      const rg = within(g).getByRole("radiogroup", { name: e.radiogroup });
      const radios = within(rg).getAllByRole("radio");
      expect(radios.map((r) => r.textContent)).toEqual(e.options);
      for (const opt of e.options) expect(within(rg).getByRole("radio", { name: opt })).toBeInTheDocument(); // by NAME, not text
    }
  });

  it("invariant: no radio on the page is named after a wrapping label instead of its own text", async () => {
    mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network");
    await screen.findByRole("group", { name: "Colour by" });
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(7);
    for (const r of radios) {
      const own = (r.textContent ?? "").trim();
      expect(screen.getAllByRole("radio", { name: own }).includes(r)).toBe(true); // its accessible name resolves from its own text
    }
    expect(screen.queryByRole("radio", { name: /Colour by|Depth|Edges/ })).toBeNull();
  });
});

describe("Network page: selecting each option really changes what is shown / requested", () => {
  it("Colour: Risk is checked by default; choosing Community checks it, unchecks Risk and reveals community info", async () => {
    mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network");
    const risk = await screen.findByRole("radio", { name: "Risk" });
    const comm = screen.getByRole("radio", { name: "Community" });
    expect(risk).toBeChecked(); expect(comm).not.toBeChecked();
    await waitFor(() => expect(screen.getByText(/3 accounts · 2 edges/)).toBeInTheDocument());
    expect(screen.queryByText(/communities in dataset/)).toBeNull();           // risk mode: no community summary
    await userEvent.click(comm);
    expect(screen.getByRole("radio", { name: "Community" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Risk" })).not.toBeChecked();
    expect(screen.getByText(/7 communities in dataset \(weak structure\)/)).toBeInTheDocument(); // community mode: shown
    await userEvent.click(screen.getByRole("radio", { name: "Risk" }));
    expect(screen.getByRole("radio", { name: "Risk" })).toBeChecked();
    expect(screen.queryByText(/communities in dataset/)).toBeNull();           // and gone again
  });

  it("Colour mode starts as Community when the URL says so", async () => {
    mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network?color=community");
    expect(await screen.findByRole("radio", { name: "Community" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Risk" })).not.toBeChecked();
  });

  it("Edges: choosing Individual re-requests the graph with mode=transactions", async () => {
    const f = mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network");
    await waitFor(() => expect(calls(f).length).toBeGreaterThan(0));
    expect(calls(f).every((u) => !u.includes("mode=transactions"))).toBe(true);
    await userEvent.click(screen.getByRole("radio", { name: "Individual" }));
    expect(screen.getByRole("radio", { name: "Individual" })).toBeChecked();
    await waitFor(() => expect(calls(f).some((u) => u.includes("mode=transactions"))).toBe(true));
  });

  it("Depth: choosing 2 hops is reflected in the request for a focused account", async () => {
    const f = mockApi(routes());
    renderWithProviders(<NetworkPage />, "/network?account=A");
    await waitFor(() => expect(calls(f).some((u) => u.includes("center=A") && u.includes("depth=1"))).toBe(true));
    await userEvent.click(screen.getByRole("radio", { name: "2" }));
    await waitFor(() => expect(calls(f).some((u) => u.includes("center=A") && u.includes("depth=2"))).toBe(true));
  });
});
