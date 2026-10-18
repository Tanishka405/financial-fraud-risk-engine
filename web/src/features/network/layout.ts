import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force";
import type { GraphData } from "@/api/types";

export interface Pos { x: number; y: number; r: number }
interface N extends SimulationNodeDatum { id: string; r: number }

/** Radius scales with degree relative to this graph's min/max so size differences stay visible (8-28px). */
export function radiusScale(graph: GraphData): (degree: number) => number {
  const ds = graph.nodes.map((n) => n.degree_total);
  const lo = Math.min(...ds, 0), hi = Math.max(...ds, 1);
  return (d) => 8 + 20 * Math.pow(Math.max(0, d - lo) / Math.max(hi - lo, 1), 0.65);
}

/** Deterministic force layout (d3-force uses a seeded LCG). Centre account is pinned at the origin. */
export function computeLayout(g: GraphData): Map<string, Pos> {
  const rad = radiusScale(g);
  const nodes: N[] = g.nodes.map((n) => ({ id: n.id, r: rad(n.degree_total), ...(n.is_center ? { fx: 0, fy: 0 } : {}) }));
  const ids = new Set(nodes.map((n) => n.id));
  const seen = new Set<string>();
  const links: SimulationLinkDatum<N>[] = [];
  for (const e of g.edges) {
    const k = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
    if (seen.has(k) || !ids.has(e.source) || !ids.has(e.target)) continue;
    seen.add(k); links.push({ source: e.source, target: e.target });
  }
  const n = Math.max(nodes.length, 1);
  const sim = forceSimulation(nodes)
    .force("link", forceLink<N, SimulationLinkDatum<N>>(links).id((d) => d.id).distance(70 + Math.min(n, 120) * 0.6).strength(0.35))
    .force("charge", forceManyBody().strength(-180 - Math.min(n, 150) * 2))
    .force("collide", forceCollide<N>((d) => d.r + 10))
    .force("x", forceX(0).strength(0.05)).force("y", forceY(0).strength(0.05))
    .stop();
  for (let i = 0; i < 320; i++) sim.tick();
  return new Map(nodes.map((d) => [d.id, { x: d.x ?? 0, y: d.y ?? 0, r: d.r }]));
}

export function edgeWidth(amount: number): number { return Math.max(1, Math.min(5, 0.6 + Math.log10(1 + amount / 1000) * 1.15)); }

/** Perpendicular offsets for parallel / antiparallel edges so none are drawn on top of another. */
export function parallelOffsets(edges: { id: string; source: string; target: string }[]): Map<string, number> {
  const groups = new Map<string, string[]>();
  for (const e of edges) { const k = `${e.source}>${e.target}`; (groups.get(k) ?? groups.set(k, []).get(k)!).push(e.id); }
  const out = new Map<string, number>();
  for (const [k, ids] of groups) {
    const [s, t] = k.split(">");
    const hasReverse = groups.has(`${t}>${s}`);
    ids.forEach((id, i) => out.set(id, (hasReverse ? 12 : 0) + (i - (ids.length - 1) / 2) * 14));
  }
  return out;
}
