import type { GraphAnalyticsBlock } from "@/api/types";
import { SignalKind } from "@/components/domain/badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { Tip } from "@/components/ui/Tooltip";
import { int, num } from "@/lib/format";
import { communityColor } from "@/features/network/palette";

const HELP = {
  pagerank: "Importance from the flow of funds into the account, weighted by INR amount (PageRank). Percentile is relative to other accounts in this dataset.",
  betweenness: "How often the account lies on shortest paths between other accounts (unweighted). 0 means it never bridges other accounts.",
  community: "Group of accounts that transact more with each other than with the rest (seeded Louvain on transaction counts).",
} as const;

export function GraphStructureCard({ g }: { g: GraphAnalyticsBlock | null }) {
  return (
    <Card>
      <CardHeader title="Graph structure" right={<SignalKind kind="computed" />} subtitle="Position in the transaction network" />
      {g === null ? (
        <p className="px-4 pb-4 text-[13px] text-fg-3">Graph analytics are unavailable for this dataset. Detection and scores are unaffected.</p>
      ) : (
        <div className="px-4 pb-3">
          <dl className="divide-y divide-line text-[13px]">
            <div className="flex items-baseline justify-between gap-3 py-1.5"><dt className="flex items-center gap-1 text-fg-3">PageRank <Tip text={HELP.pagerank} /></dt><dd className="num text-right text-fg">{g.pagerank.toFixed(4)} <span className="text-fg-3">· p{num(g.pagerank_percentile, 0)}</span></dd></div>
            <div className="flex items-baseline justify-between gap-3 py-1.5"><dt className="flex items-center gap-1 text-fg-3">Betweenness <Tip text={HELP.betweenness} /></dt><dd className="num text-right text-fg">{g.betweenness.toFixed(4)} <span className="text-fg-3">· p{num(g.betweenness_percentile, 0)}</span></dd></div>
            <div className="flex items-baseline justify-between gap-3 py-1.5"><dt className="flex items-center gap-1 text-fg-3">Community <Tip text={HELP.community} /></dt>
              <dd className="num flex items-center gap-1.5 text-right text-fg"><i className="inline-block size-2.5 rounded-full" style={{ background: communityColor(g.community_id) }} aria-hidden />#{g.community_id} · {int(g.community_size)} {g.community_size === 1 ? "account" : "accounts"}</dd></div>
          </dl>
          {g.community_size <= 2 && <p className="mt-2 text-xs text-fg-3">Very small group: this account is only connected to {g.community_size === 1 ? "no one in a group" : "one other account"} in the community structure.</p>}
          {g.modularity !== null && g.modularity < 0.3 && <p className="mt-2 text-xs text-amber">Weak community structure in this dataset (modularity {g.modularity.toFixed(2)}): group membership may be largely arbitrary.</p>}
          <p className="mt-2 text-2xs leading-snug text-fg-3">{g.note}{g.betweenness_method !== "exact" && ` Betweenness method: ${g.betweenness_method}.`}</p>
        </div>
      )}
    </Card>
  );
}
