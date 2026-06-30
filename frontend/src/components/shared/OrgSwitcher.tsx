"use client";

import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth.store";

export function OrgSwitcher() {
  const { organization, pendingOrgs, selectOrg } = useAuthStore();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!pendingOrgs || pendingOrgs.length === 0) return null;

  async function handleSelect(orgId: string) {
    setLoading(true);
    setError(null);
    try {
      await selectOrg(orgId, password);
    } catch {
      setError("Failed to switch organization. Check your password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md">
        <h2 className="text-xl font-semibold mb-4">Select Organization</h2>
        <p className="text-sm text-gray-600 mb-4">
          You belong to multiple organizations. Choose one to continue.
        </p>
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confirm password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Your password"
          />
        </div>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <ul className="space-y-2">
          {pendingOrgs.map((org) => (
            <li key={org.id}>
              <button
                onClick={() => handleSelect(org.id)}
                disabled={loading || !password}
                className="w-full text-left border rounded-lg px-4 py-3 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                <span className="font-medium">{org.name}</span>
                <span className="ml-2 text-xs text-gray-500">({org.plan})</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
