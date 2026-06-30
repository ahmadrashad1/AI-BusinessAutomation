"use client";

import { NODE_TYPE_DEFS, type NodeTypeDef } from "@/types/workflow";

interface NodePaletteProps {
  onDragStart: (e: React.DragEvent, def: NodeTypeDef) => void;
}

export function NodePalette({ onDragStart }: NodePaletteProps) {
  const triggers = NODE_TYPE_DEFS.filter((d) => d.category === "trigger");
  const actions = NODE_TYPE_DEFS.filter((d) => d.category === "action");

  return (
    <aside className="w-56 flex-none border-r bg-gray-50 overflow-y-auto">
      <div className="p-3">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Nodes</h2>

        <p className="mb-1 text-[10px] font-medium uppercase text-violet-600">Triggers</p>
        <div className="mb-4 space-y-1">
          {triggers.map((def) => (
            <div
              key={def.type}
              draggable
              onDragStart={(e) => onDragStart(e, def)}
              className="flex cursor-grab items-center gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-medium text-violet-800 hover:bg-violet-100 active:cursor-grabbing"
            >
              {def.label}
            </div>
          ))}
        </div>

        <p className="mb-1 text-[10px] font-medium uppercase text-blue-600">Actions</p>
        <div className="space-y-1">
          {actions.map((def) => (
            <div
              key={def.type}
              draggable
              onDragStart={(e) => onDragStart(e, def)}
              className="flex cursor-grab items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-800 hover:bg-blue-100 active:cursor-grabbing"
            >
              {def.label}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
