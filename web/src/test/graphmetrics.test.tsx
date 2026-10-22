import { screen } from "@testing-library/react";
import type { GraphAnalyticsBlock, GraphNode } from "@/api/types";
import { GraphStructureCard } from "@/components/domain/GraphStructureCard";
import { Legend } from "@/features/network/Legend";
import { nodeFill, nodeRing } from "@/features/network/NetworkGraph";
import { COMMUNITY_PALETTE, communityColor } from "@/features/network/palette";
import { NEUTRAL_NODE } from "@/lib/tokens";
import { renderWithProviders } from "./utils";

const block = (o: Partial<GraphAnalyticsBlock> = {}): GraphAnalyticsBlock => ({
  pagerank: 0.0123, pagerank_percentile: 87.4, betweenness: 0.0042, betweenness_percentile: 61.2, community_id: 3, community_size: 14,
  n_communities: 7, modularity: 0.42, betweenness_method: "exact", note: "Structural metrics … NOT risk signals: excluded from the risk score.", ...o,
});
const node = (o: Partial<GraphNode> = {}): GraphNode => ({
  id: "A", is_center: false, risk_score: 10, severity: "high", has_alert: true, reason_codes: [], community_id: 2, degree_total: 5, counterparties: 3,
  visible_in: 1, visible_out: 1, visible_in_inr: 1, visible_out_inr: 1, ...o,
});

describe("community palette", () => {
  it("is stable, wraps every 8, and falls back to neutral for missing/invalid ids", () => {
    expect(communityColor(0)).toBe(COMMUNITY_PALETTE[0]);
    expect(communityColor(8)).toBe(communityColor(0));
    expect(communityColor(3)).toBe(communityColor(3));
    for (const bad of [null, undefined, -1, 1.5, Number.NaN]) expect(communityColor(bad as number | null)).toBe(NEUTRAL_NODE);
    expect(new Set(COMMUNITY_PALETTE).size).toBe(COMMUNITY_PALETTE.length);
  });
});

describe("node fill / ring by colour mode", () => {
  it("risk mode colours alerted nodes by severity and others neutral, with no ring", () => {
    expect(nodeFill(node(), "risk")).toBe("#f87171");
    expect(nodeFill(node({ has_alert: false, severity: "low" }), "risk")).toBe(NEUTRAL_NODE);
    expect(nodeRing(node(), "risk")).toBeNull();
  });
  it("community mode fills by community and keeps severity visible as a ring on alerted accounts only", () => {
    expect(nodeFill(node({ community_id: 2 }), "community")).toBe(communityColor(2));
    expect(nodeRing(node(), "community")).toBe("#f87171");
    expect(nodeRing(node({ has_alert: false }), "community")).toBeNull();
    expect(nodeFill(node({ community_id: null }), "community")).toBe(NEUTRAL_NODE);
  });
});

describe("GraphStructureCard", () => {
  it("shows PageRank, betweenness, percentiles and the community, with the not-a-risk-signal note", () => {
    renderWithProviders(<GraphStructureCard g={block()} />);
    expect(screen.getByText(/0\.0123/)).toBeInTheDocument();
    expect(screen.getByText(/p87/)).toBeInTheDocument();
    expect(screen.getByText(/p61/)).toBeInTheDocument();
    expect(screen.getByText(/#3 · 14 accounts/)).toBeInTheDocument();
    expect(screen.getByText(/NOT risk signals/)).toBeInTheDocument();
    expect(screen.queryByText(/Weak community structure/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Betweenness method/)).not.toBeInTheDocument();
  });
  it("is graceful when analytics are unavailable", () => {
    renderWithProviders(<GraphStructureCard g={null} />);
    expect(screen.getByText(/unavailable for this dataset/)).toBeInTheDocument();
    expect(screen.getByText(/scores are unaffected/)).toBeInTheDocument();
  });
  it("explains tiny communities and a weak overall structure, and discloses approximate betweenness", () => {
    renderWithProviders(<GraphStructureCard g={block({ community_size: 2, modularity: 0.15, betweenness_method: "sampled(k=100)", betweenness: 0, betweenness_percentile: 0 })} />);
    expect(screen.getByText(/Very small group/)).toBeInTheDocument();
    expect(screen.getByText(/only connected to one other account/)).toBeInTheDocument();
    expect(screen.getByText(/Weak community structure/)).toHaveTextContent("0.15");
    expect(screen.getByText(/Betweenness method: sampled\(k=100\)/)).toBeInTheDocument();
    expect(screen.getByText(/0\.0000/)).toBeInTheDocument(); // zero betweenness renders as a number, not blank
  });
  it("uses singular wording for a one-account community", () => {
    renderWithProviders(<GraphStructureCard g={block({ community_size: 1, modularity: null })} />);
    expect(screen.getByText(/#3 · 1 account$/)).toBeInTheDocument();
  });
});

describe("Legend", () => {
  it("explains risk colours by default and community colouring (with ring) when selected", () => {
    const { rerender } = renderWithProviders(<Legend mode="aggregated" />);
    expect(screen.getByText(/Critical severity alert/)).toBeInTheDocument();
    rerender(<Legend mode="aggregated" colorBy="community" />);
    expect(screen.queryByText(/Critical severity alert/)).not.toBeInTheDocument();
    expect(screen.getByText(/palette repeats every 8/)).toBeInTheDocument();
    expect(screen.getByText(/not risk signals/)).toBeInTheDocument();
  });
});
