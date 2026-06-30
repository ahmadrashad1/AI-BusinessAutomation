"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Pencil, RotateCcw } from "lucide-react";
import { useWorkflow, useWorkflowVersions, useRevertWorkflow } from "@/lib/query/useWorkflows";
import { PermissionGate } from "@/components/shared/PermissionGate";

interface Props {
  params: Promise<{ id: string }>;
}

export default function WorkflowDetailPage({ params }: Props) {
  const { id } = use(params);
  const { data: workflow, isLoading } = useWorkflow(id);
  const { data: versions } = useWorkflowVersions(id);
  const revertMutation = useRevertWorkflow(id);

  if (isLoading) {
    return <div className="p-6 text-sm text-gray-400">Loading…</div>;
  }

  if (!workflow) {
    return <div className="p-6 text-sm text-red-500">Workflow not found.</div>;
  }

  const statusColor =
    workflow.status === "published" ? "bg-green-100 text-green-700"
    : workflow.status === "archived" ? "bg-gray-100 text-gray-500"
    : "bg-amber-100 text-amber-700";

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/workflows" className="text-gray-400 hover:text-gray-700">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{workflow.name}</h1>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${statusColor}`}>
              {workflow.status}
            </span>
          </div>
          {workflow.description && (
            <p className="mt-1 text-sm text-gray-500">{workflow.description}</p>
          )}
        </div>
        <PermissionGate minRole="manager">
          <Link
            href={`/workflows/${id}/builder`}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Pencil className="h-4 w-4" />
            Open Builder
          </Link>
        </PermissionGate>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="text-xs text-gray-500 mb-1">Current version</p>
          <p className="text-2xl font-bold text-gray-900">
            {workflow.current_version ? `v${workflow.current_version}` : "—"}
          </p>
        </div>
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="text-xs text-gray-500 mb-1">Created</p>
          <p className="text-sm font-medium text-gray-700">
            {new Date(workflow.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="text-xs text-gray-500 mb-1">Last updated</p>
          <p className="text-sm font-medium text-gray-700">
            {new Date(workflow.updated_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Version history */}
      <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-700">Version History</h2>
        </div>
        {!versions || versions.total === 0 ? (
          <p className="px-4 py-6 text-sm text-gray-400">No published versions yet. Open the builder to publish.</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Published</th>
                <th className="px-4 py-3">Nodes</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {versions.items.map((ver) => (
                <tr key={ver.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">
                    v{ver.version_number}
                    {ver.version_number === workflow.current_version && (
                      <span className="ml-2 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold text-green-700">
                        Active
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(ver.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {ver.definition.nodes.length} nodes, {ver.definition.edges.length} edges
                  </td>
                  <td className="px-4 py-3">
                    <PermissionGate minRole="admin">
                      {ver.version_number !== workflow.current_version && (
                        <button
                          onClick={() => {
                            if (confirm(`Revert to v${ver.version_number}? This will create a new version.`)) {
                              revertMutation.mutate(ver.version_number);
                            }
                          }}
                          disabled={revertMutation.isPending}
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-blue-600"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Revert
                        </button>
                      )}
                    </PermissionGate>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
