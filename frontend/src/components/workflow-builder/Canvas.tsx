"use client";

import { useCallback, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type NodeTypes,
  type OnNodeClick,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useBuilderStore } from "@/lib/stores/builder.store";
import { TriggerNode } from "./nodes/TriggerNode";
import { ActionNode } from "./nodes/ActionNode";
import { ConditionNode } from "./nodes/ConditionNode";
import type { NodeTypeDef } from "@/types/workflow";

const nodeTypes: NodeTypes = {
  triggerNode: TriggerNode,
  actionNode: ActionNode,
  conditionNode: ConditionNode,
};

export function Canvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, selectNode, addNode } =
    useBuilderStore();

  const wrapperRef = useRef<HTMLDivElement>(null);

  const onNodeClick: OnNodeClick = useCallback(
    (_, node) => selectNode(node.id),
    [selectNode]
  );

  const onPaneClick = useCallback(() => selectNode(null), [selectNode]);

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const raw = e.dataTransfer.getData("application/workflow-node");
    if (!raw) return;

    const def: NodeTypeDef = JSON.parse(raw);
    const bounds = wrapperRef.current?.getBoundingClientRect();
    if (!bounds) return;

    const position = {
      x: e.clientX - bounds.left - 80,
      y: e.clientY - bounds.top - 30,
    };

    const id = `node-${Date.now()}`;
    const rfType =
      def.type.startsWith("trigger.") ? "triggerNode"
      : def.type === "action.condition" ? "conditionNode"
      : "actionNode";

    addNode({
      id,
      type: rfType,
      position,
      data: { nodeType: def.type, label: def.label, config: {} },
    });
    selectNode(id);
  }

  return (
    <div
      ref={wrapperRef}
      className="flex-1 h-full"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode="Delete"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
