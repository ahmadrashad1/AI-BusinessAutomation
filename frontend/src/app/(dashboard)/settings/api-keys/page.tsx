"use client";

import { useState } from "react";
import {
  useAPIKeys,
  useCreateAPIKey,
  useRevokeAPIKey,
} from "@/lib/query/useOrganizations";
import { PermissionGate } from "@/components/shared/PermissionGate";

const AVAILABLE_SCOPES = [
  "workflow:read",
  "workflow:execute",
  "analytics:read",
  "reports:read",
];

export default function APIKeysPage() {
  const { data: apiKeys = [], isLoading } = useAPIKeys();
  const createKey = useCreateAPIKey();
  const revokeKey = useRevokeAPIKey();

  const [label, setLabel] = useState("");
  const [scopes, setScopes] = useState<string[]>(["workflow:read"]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleScope(scope: string) {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNewKey(null);
    try {
      const result = await createKey.mutateAsync({ label, scopes });
      setNewKey(result.key);
      setLabel("");
      setScopes(["workflow:read"]);
    } catch (err: any) {
      setError(err?.response?.data?.error?.message ?? "Failed to create API key.");
    }
  }

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold mb-1">API Keys</h1>
        <p className="text-sm text-gray-500">
          Create and manage API keys for programmatic access.
        </p>
      </div>

      <PermissionGate minRole="admin">
        <div className="bg-white border rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold">Create New API Key</h2>

          {newKey && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-xs font-medium text-green-800 mb-2">
                Copy this key — it will not be shown again.
              </p>
              <code className="block text-xs font-mono bg-white border rounded px-3 py-2 break-all">
                {newKey}
              </code>
            </div>
          )}

          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Label</label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Production Integration"
                required
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Scopes</label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_SCOPES.map((scope) => (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => toggleScope(scope)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      scopes.includes(scope)
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                    }`}
                  >
                    {scope}
                  </button>
                ))}
              </div>
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={createKey.isPending || scopes.length === 0}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {createKey.isPending ? "Creating…" : "Create API Key"}
            </button>
          </form>
        </div>
      </PermissionGate>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Label</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Prefix</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Scopes</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Created</th>
              <PermissionGate minRole="admin">
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </PermissionGate>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading…</td>
              </tr>
            ) : apiKeys.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No API keys yet.
                </td>
              </tr>
            ) : (
              apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{key.label}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{key.key_prefix}…</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {key.scopes.map((s) => (
                        <span
                          key={s}
                          className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-700"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <PermissionGate minRole="admin">
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => revokeKey.mutate(key.id)}
                        className="text-red-600 hover:underline text-xs"
                      >
                        Revoke
                      </button>
                    </td>
                  </PermissionGate>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
