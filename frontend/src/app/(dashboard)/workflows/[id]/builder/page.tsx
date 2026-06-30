"use client";

import { use, useEffect } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { useWorkflow } from "@/lib/query/useWorkflows";
import { useBuilderStore } from "@/lib/stores/builder.store";
import { Canvas } from "@/components/workflow-builder/Canvas";
import { NodePalette } from "@/components/workflow-builder/NodePalette";
import { NodeConfigPanel } from "@/components/workflow-builder/NodeConfigPanel";
import { Toolbar } from "@/components/workflow-builder/Toolbar";
import type { NodeTypeDef } from "@/types/workflow";

interface Props {
  params: Promise<{ id: string }>;
}

function BuilderInner({ id }: { id: string }) {
  const { data: workflow, isLoading } = useWorkflow(id);
  const { loadGraph, reset } = useBuilderStore();

  // Load the saved draft_definition into the canvas when workflow loads
  useEffect(() => {
    if (workflow) {
      loadGraph(id, workflow.draft_definition);
    }
    return () => reset();
  }, [workflow?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleDragStart(e: React.DragEvent, def: NodeTypeDef) {
    e.dataTransfer.setData("application/workflow-node", JSON.stringify(def));
    e.dataTransfer.effectAllowed = "move";
  }

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-gray-400">
        Loading workflow…
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-red-500">
        Workflow not found.
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Toolbar
        workflowId={id}
        workflowName={workflow.name}
        status={workflow.status}
      />
      <div className="flex flex-1 overflow-hidden">
        <NodePalette onDragStart={handleDragStart} />
        <Canvas />
        <NodeConfigPanel />
      </div>
    </div>
  );
}

export default function BuilderPage({ params }: Props) {
  const { id } = use(params);

  return (
    <ReactFlowProvider>
      <BuilderInner id={id} />
    </ReactFlowProvider>
  );
}
