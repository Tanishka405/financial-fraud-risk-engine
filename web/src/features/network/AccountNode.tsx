import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface AccountNodeData extends Record<string, unknown> {
  label: string; r: number; color: string; center: boolean; selected: boolean; dim: boolean; showLabel: boolean; alert: boolean;
}
const hid = { opacity: 0, left: "50%", top: "50%", width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0 } as const;

export function AccountNode({ data }: NodeProps) {
  const d = data as AccountNodeData;
  const size = d.r * 2;
  return (
    <div style={{ width: size, height: size, opacity: d.dim ? 0.3 : 1 }} className="relative transition-opacity" title={d.label}>
      <Handle type="target" position={Position.Top} style={hid} isConnectable={false} />
      <Handle type="source" position={Position.Top} style={hid} isConnectable={false} />
      <div style={{ background: d.color, boxShadow: d.selected ? `0 0 0 3px #0b1120, 0 0 0 5px #22d3ee` : d.center ? `0 0 0 2px #0b1120, 0 0 0 3.5px ${d.color}` : d.alert ? `0 0 14px ${d.color}55` : "none" }}
        className="size-full rounded-full border border-white/10" />
      {d.showLabel && <span style={{ top: size + 3 }} className="pointer-events-none absolute left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[10px] text-fg-2">{d.label}</span>}
    </div>
  );
}
