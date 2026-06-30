"use client";

import { useState } from "react";
import { Save, Upload, RotateCcw, AlertCircle, CheckCircle2 } from "lucide-react";
import { useBuilderStore } from "@/lib/stores/builder.store";
import { useUpdateWorkflow, usePublishWorkflow } from "@/lib/query/useWorkflows";
import type { ApiError, ValidationError } from "@/types/workflow";
import axios from "axios";

interface ToolbarProps {
  workflowId: string;
  workflowName: string;
  status: string;
}

export function Toolbar({ workflowId, workflowName, status }: ToolbarProps) {
  const { isDirty, toGraph, setValidationErrors, clearValidationErrors } = useBuilderStore();
  const updateMutation = useUpdateWorkflow(workflowId);
  const publishMutation = usePublishWorkflow(workflowId);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [publishErrors, setPublishErrors] = useState<ValidationError[]>([]);

  async function handleSaveDraft() {
    setSaveState("saving");
    clearValidationErrors();
    try {
      await updateMutation.mutateAsync({ definition: toGraph() });
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch {
      setSaveState("error");
    }
  }

  async function handlePublish() {
    clearValidationErrors();
    setPublishErrors([]);
    try {
      // Save draft first, then publish using stored definition
      await updateMutation.mutateAsync({ definition: toGraph() });
      await publishMutation.mutateAsync();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const apiErr = err.response.data as ApiError;
        const errors = apiErr?.error?.details?.errors ?? [];
        setPublishErrors(errors);
        setValidationErrors(errors);
      }
    }
  }

  const statusColor =
    status === "published" ? "text-green-600 bg-green-50 border-green-200"
    : status === "archived" ? "text-gray-500 bg-gray-50 border-gray-200"
    : "text-amber-600 bg-amber-50 border-amber-200";

  return (
    <div className="flex items-center justify-between border-b bg-white px-4 py-2 shadow-sm">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-gray-800">{workflowName}</h1>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${statusColor}`}>
          {status}
        </span>
        {isDirty && <span className="text-[10px] text-gray-400">Unsaved changes</span>}
      </div>

      <div className="flex items-center gap-2">
        {publishErrors.length > 0 && (
          <div className="flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1">
            <AlertCircle className="h-3.5 w-3.5 text-red-500" />
            <span className="text-[11px] text-red-600">{publishErrors.length} validation error(s)</span>
          </div>
        )}

        {saveState === "saved" && (
          <div className="flex items-center gap-1 text-green-600">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span className="text-xs">Saved</span>
          </div>
        )}

        <button
          onClick={handleSaveDraft}
          disabled={!isDirty || saveState === "saving"}
          className="flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
        >
          <Save className="h-3.5 w-3.5" />
          {saveState === "saving" ? "Saving…" : "Save Draft"}
        </button>

        <button
          onClick={handlePublish}
          disabled={publishMutation.isPending || updateMutation.isPending}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Upload className="h-3.5 w-3.5" />
          {publishMutation.isPending ? "Publishing…" : "Publish"}
        </button>
      </div>
    </div>
  );
}
