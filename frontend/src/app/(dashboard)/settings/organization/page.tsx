"use client";

import { useState } from "react";
import { useOrg, useUpdateOrg } from "@/lib/query/useOrganizations";
import { usePermission } from "@/lib/hooks/usePermission";
import { PermissionGate } from "@/components/shared/PermissionGate";

export default function OrganizationSettingsPage() {
  const { data: org, isLoading } = useOrg();
  const updateOrg = useUpdateOrg();
  const canEdit = usePermission("admin");

  const [name, setName] = useState("");
  const [saved, setSaved] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateOrg.mutate({ name }, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      },
    });
  }

  if (isLoading) {
    return <div className="p-6 text-sm text-gray-500">Loading…</div>;
  }

  if (!org) {
    return <div className="p-6 text-sm text-red-500">Organization not found.</div>;
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-semibold mb-1">Organization Settings</h1>
      <p className="text-sm text-gray-500 mb-6">
        Manage your organization's profile and preferences.
      </p>

      <div className="bg-white border rounded-xl p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            type="text"
            defaultValue={org.name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canEdit}
            className="w-full border rounded-lg px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Slug</label>
          <input
            type="text"
            value={org.slug}
            disabled
            className="w-full border rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500"
          />
          <p className="text-xs text-gray-400 mt-1">Slug cannot be changed after creation.</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plan</label>
          <input
            type="text"
            value={org.plan}
            disabled
            className="w-full border rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500"
          />
        </div>

        <PermissionGate minRole="admin">
          <form onSubmit={handleSubmit}>
            <button
              type="submit"
              disabled={updateOrg.isPending || !name || name === org.name}
              className="mt-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {updateOrg.isPending ? "Saving…" : saved ? "Saved!" : "Save Changes"}
            </button>
          </form>
        </PermissionGate>
      </div>

      <div className="mt-6 bg-white border rounded-xl p-6">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Storage</h2>
        <p className="text-sm text-gray-500">
          {(org.storage_used_bytes / 1024 / 1024).toFixed(1)} MB used
        </p>
      </div>
    </div>
  );
}
