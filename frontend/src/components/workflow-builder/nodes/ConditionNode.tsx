"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { GitBranch } from "lucide-react";
import { useBuilderStore } from "@/lib/stores/builder.store";

export function ConditionNode({ id, data, selected }: NodeProps) {
  const errors = useBuilderStore((s) => s.validationErrors.filter((e) => e.node_id === id));

  return (
    <div
      className={`
        min-w-[160px] rounded-lg border-2 bg-white shadow-sm cursor-pointer
        ${selected ? "border-amber-500 shadow-amber-200" : "border-amber-300"}
        ${errors.length > 0 ? "border-red-500" : ""}
      `}
    >
      <div className="flex items-center gap-2 rounded-t-md bg-amber-50 px-3 py-2 border-b border-amber-200">
        <GitBranch className="h-3.5 w-3.5 text-amber-600" />
        <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-600">Condition</span>
      </div>
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-gray-800">{data.label as string}</p>
        <p className="text-[11px] text-gray-400">action.condition</p>
      </div>
      {errors.map((e, i) => (
        <p key={i} className="px-3 pb-2 text-[10px] text-red-500">{e.message}</p>
      ))}
      <Handle type="target" position={Position.Left} id="input" className="!bg-amber-400" />
      {/* True branch — top-right */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: "35%" }}
        className="!bg-green-400"
      />
      {/* False branch — bottom-right */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: "65%" }}
        className="!bg-red-400"
      />
    </div>
  );
}
