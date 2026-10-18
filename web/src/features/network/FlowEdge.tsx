import { BaseEdge, EdgeLabelRenderer, type EdgeProps } from "@xyflow/react";

export interface FlowEdgeData extends Record<string, unknown> {
  offset: number; width: number; color: string; dim: boolean; label?: string; sR: number; tR: number; emphasis: boolean; onHover?: (id: string | null) => void;
}

export function FlowEdge({ id, sourceX, sourceY, targetX, targetY, markerEnd, data }: EdgeProps) {
  const d = data as FlowEdgeData;
  const dx = targetX - sourceX, dy = targetY - sourceY, len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len, px = -uy, py = ux;
  const sx = sourceX + ux * d.sR, sy = sourceY + uy * d.sR, ex = targetX - ux * (d.tR + 3), ey = targetY - uy * (d.tR + 3);
  const cx = (sx + ex) / 2 + px * d.offset * 2, cy = (sy + ey) / 2 + py * d.offset * 2;
  const path = `M ${sx} ${sy} Q ${cx} ${cy} ${ex} ${ey}`;
  const lx = 0.25 * sx + 0.5 * cx + 0.25 * ex, ly = 0.25 * sy + 0.5 * cy + 0.25 * ey;
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ stroke: d.color, strokeWidth: d.width, opacity: d.dim ? 0.12 : d.emphasis ? 0.95 : 0.4 }} interactionWidth={14} />
      {d.label && !d.dim && (
        <EdgeLabelRenderer>
          <div style={{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }} className="num pointer-events-none absolute rounded border border-line-strong bg-s2/95 px-1 py-px text-[10px] text-fg-2">{d.label}</div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
