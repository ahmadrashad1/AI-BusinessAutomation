"use client";

import { useState } from "react";
import {
  useMembers,
  useInvitations,
  useInviteMember,
  useUpdateMember,
  useRemoveMember,
  useRevokeInvitation,
} from "@/lib/query/useOrganizations";
import { useOrg } from "@/lib/hooks/useOrg";
import { PermissionGate } from "@/components/shared/PermissionGate";
import { useAuthStore } from "@/lib/stores/auth.store";

const ASSIGNABLE_ROLES = ["admin", "manager", "analyst", "employee", "viewer"];

export default function MembersPage() {
  const orgId = useOrg()?.id ?? null;
  const currentUserId = useAuthStore((s) => s.user?.id);

  const { data: members = [], isLoading: membersLoading } = useMembers();
  const { data: invitations = [], isLoading: invitationsLoading } = useInvitations();

  const inviteMember = useInviteMember();
  const updateMember = useUpdateMember();
  const removeMember = useRemoveMember();
  const revokeInvitation = useRevokeInvitation();

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError(null);
    try {
      await inviteMember.mutateAsync({ email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      setInviteSuccess(true);
      setTimeout(() => setInviteSuccess(false), 3000);
    } catch (err: any) {
      setInviteError(err?.response?.data?.error?.message ?? "Failed to send invitation.");
    }
  }

  return (
    <div className="p-6 max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold mb-1">Members</h1>
        <p className="text-sm text-gray-500">Manage who has access to your organization.</p>
      </div>

      {/* Invite section */}
      <PermissionGate minRole="manager">
        <div className="bg-white border rounded-xl p-6">
          <h2 className="text-sm font-semibold mb-4">Invite Member</h2>
          <form onSubmit={handleInvite} className="flex gap-3">
            <input
              type="email"
              placeholder="Email address"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              required
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm"
            >
              {ASSIGNABLE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={inviteMember.isPending}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {inviteMember.isPending ? "Sending…" : "Send Invite"}
            </button>
          </form>
          {inviteError && <p className="text-xs text-red-600 mt-2">{inviteError}</p>}
          {inviteSuccess && <p className="text-xs text-green-600 mt-2">Invitation sent!</p>}
        </div>
      </PermissionGate>

      {/* Members list */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">User</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Role</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Joined</th>
              <PermissionGate minRole="manager">
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </PermissionGate>
            </tr>
          </thead>
          <tbody className="divide-y">
            {membersLoading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : (
              members.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{m.user_id}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {m.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(m.joined_at).toLocaleDateString()}
                  </td>
                  <PermissionGate minRole="manager">
                    <td className="px-4 py-3 text-right">
                      {m.user_id !== currentUserId && m.role !== "owner" && (
                        <button
                          onClick={() => removeMember.mutate(m.user_id)}
                          className="text-red-600 hover:underline text-xs"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  </PermissionGate>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pending invitations */}
      <PermissionGate minRole="manager">
        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">Pending Invitations</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Email</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Role</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Expires</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {invitationsLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-gray-400">Loading…</td>
                </tr>
              ) : invitations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-gray-400">
                    No pending invitations.
                  </td>
                </tr>
              ) : (
                invitations.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">{inv.email}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        {inv.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(inv.expires_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => revokeInvitation.mutate(inv.id)}
                        className="text-red-600 hover:underline text-xs"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </PermissionGate>
    </div>
  );
}
