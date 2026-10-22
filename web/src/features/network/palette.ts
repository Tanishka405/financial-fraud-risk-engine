import { NEUTRAL_NODE } from "@/lib/tokens";

/** Muted categorical palette (distinct hue and lightness). Repeats every 8 communities. */
export const COMMUNITY_PALETTE = ["#38bdf8", "#a78bfa", "#34d399", "#f59e0b", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8"] as const;

export function communityColor(id: number | null | undefined): string {
  if (id === null || id === undefined || !Number.isInteger(id) || id < 0) return NEUTRAL_NODE;
  return COMMUNITY_PALETTE[id % COMMUNITY_PALETTE.length];
}
