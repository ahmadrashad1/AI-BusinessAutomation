"use client";

import { useState } from "react";
import {
  useDepartments,
  useCreateDepartment,
  useDeleteDepartment,
} from "@/lib/query/useOrganizations";
import { PermissionGate } from "@/components/shared/PermissionGate";

export default function DepartmentsPage() {
  const { data: departments = [], isLoading } = useDepartments();
  const createDept = useCreateDepartment();
  const deleteDept = useDeleteDepartment();

  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createDept.mutateAsync({ name });
      setName("");
    } catch (err: any) {
      setError(err?.response?.data?.error?.message ?? "Failed to create department.");
    }
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold mb-1">Departments</h1>
        <p className="text-sm text-gray-500">Organize your team into departments.</p>
      </div>

      <PermissionGate minRole="manager">
        <div className="bg-white border rounded-xl p-6">
          <h2 className="text-sm font-semibold mb-4">Add Department</h2>
          <form onSubmit={handleCreate} className="flex gap-3">
            <input
              type="text"
              placeholder="Department name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={createDept.isPending}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {createDept.isPending ? "Adding…" : "Add"}
            </button>
          </form>
          {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        </div>
      </PermissionGate>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Created</th>
              <PermissionGate minRole="manager">
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </PermissionGate>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-gray-400">Loading…</td>
              </tr>
            ) : departments.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                  No departments yet.
                </td>
              </tr>
            ) : (
              departments.map((dept) => (
                <tr key={dept.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{dept.name}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(dept.created_at).toLocaleDateString()}
                  </td>
                  <PermissionGate minRole="manager">
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => deleteDept.mutate(dept.id)}
                        className="text-red-600 hover:underline text-xs"
                      >
                        Delete
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
