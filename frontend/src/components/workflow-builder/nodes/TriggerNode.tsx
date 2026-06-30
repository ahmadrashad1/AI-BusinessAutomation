"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Zap } from "lucide-react";
import { useBuilderStore } from "@/lib/stores/builder.store";

export function TriggerNode({ id, data, selected }: NodeProps) {
  const errors = useBuilderStore((s) => s.validationErrors.filter((e) => e.node_id === id));

  return (
    <div
      className={`
        min-w-[160px] rounded-lg border-2 bg-white shadow-sm cursor-pointer
        ${selected ? "border-violet-500 shadow-violet-200" : "border-violet-300"}
        ${errors.length > 0 ? "border-red-500" : ""}
      `}
    >
      <div className="flex items-center gap-2 rounded-t-md bg-violet-50 px-3 py-2 border-b border-violet-200">
        <Zap className="h-3.5 w-3.5 text-violet-600" />
        <span className="text-[10px] font-semibold uppercase tracking-wide text-violet-600">Trigger</span>
      </div>
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-gray-800">{data.label as string}</p>
        <p className="text-[11px] text-gray-400">{data.nodeType as string}</p>
      </div>
      {errors.map((e, i) => (
        <p key={i} className="px-3 pb-2 text-[10px] text-red-500">{e.message}</p>
      ))}
      <Handle type="source" position={Position.Right} id="output" className="!bg-violet-400" />
    </div>
  );
}
