"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Play, Archive, Copy, Trash2 } from "lucide-react";
import {
  useWorkflows,
  useCreateWorkflow,
  useDeleteWorkflow,
  useDuplicateWorkflow,
  useArchiveWorkflow,
} from "@/lib/query/useWorkflows";
import { PermissionGate } from "@/components/shared/PermissionGate";
import type { Workflow } from "@/types/workflow";

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "published" ? "bg-green-100 text-green-700"
    : status === "archived" ? "bg-gray-100 text-gray-500"
    : "bg-amber-100 text-amber-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${cls}`}>
      {status}
    </span>
  );
}

function CreateModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const createMutation = useCreateWorkflow();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await createMutation.mutateAsync({ name: name.trim(), description: description.trim() || undefined });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">New Workflow</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Workflow"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function WorkflowRow({ workflow }: { workflow: Workflow }) {
  const deleteMutation = useDeleteWorkflow();
  const duplicateMutation = useDuplicateWorkflow();
  const archiveMutation = useArchiveWorkflow();

  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="px-4 py-3">
        <Link href={`/workflows/${workflow.id}`} className="font-medium text-blue-600 hover:underline">
          {workflow.name}
        </Link>
        {workflow.description && (
          <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{workflow.description}</p>
        )}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={workflow.status} />
      </td>
      <td className="px-4 py-3 text-sm text-gray-500">
        {workflow.current_version ? `v${workflow.current_version}` : "—"}
      </td>
      <td className="px-4 py-3 text-sm text-gray-400">
        {new Date(workflow.updated_at).toLocaleDateString()}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <Link
            href={`/workflows/${workflow.id}/builder`}
            className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-blue-600"
            title="Open builder"
          >
            <Play className="h-3.5 w-3.5" />
          </Link>
          <PermissionGate minRole="manager">
            <button
              onClick={() => duplicateMutation.mutate({ id: workflow.id, name: `Copy of ${workflow.name}` })}
              className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
              title="Duplicate"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </PermissionGate>
          <PermissionGate minRole="admin">
            {workflow.status !== "archived" && (
              <button
                onClick={() => archiveMutation.mutate(workflow.id)}
                className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-amber-600"
                title="Archive"
              >
                <Archive className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => {
                if (confirm(`Delete "${workflow.name}"? This cannot be undone.`)) {
                  deleteMutation.mutate(workflow.id);
                }
              }}
              className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-red-600"
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </PermissionGate>
        </div>
      </td>
    </tr>
  );
}

export default function WorkflowsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { data, isLoading, isError } = useWorkflows();

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="mt-1 text-sm text-gray-500">
            Build, publish, and manage automated business processes.
          </p>
        </div>
        <PermissionGate minRole="manager">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            New Workflow
          </button>
        </PermissionGate>
      </div>

      {isLoading && (
        <div className="py-12 text-center text-sm text-gray-400">Loading workflows…</div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          Failed to load workflows. Please try again.
        </div>
      )}

      {data && data.total === 0 && (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-16 text-center">
          <p className="text-gray-500">No workflows yet.</p>
          <PermissionGate minRole="manager">
            <button
              onClick={() => setShowCreate(true)}
              className="mt-3 text-sm font-medium text-blue-600 hover:underline"
            >
              Create your first workflow
            </button>
          </PermissionGate>
        </div>
      )}

      {data && data.total > 0 && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((wf) => (
                <WorkflowRow key={wf.id} workflow={wf} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
