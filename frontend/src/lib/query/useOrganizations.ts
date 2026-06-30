import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  orgsApi,
  InvitePayload,
  MemberUpdatePayload,
  OrgUpdatePayload,
  DepartmentPayload,
  APIKeyPayload,
} from "@/lib/api/organizations";
import { useAuthStore } from "@/lib/stores/auth.store";

// ── query keys ─────────────────────────────────────────────────────────────────

const orgKeys = {
  detail: (orgId: string) => ["org", orgId] as const,
  members: (orgId: string) => ["org", orgId, "members"] as const,
  invitations: (orgId: string) => ["org", orgId, "invitations"] as const,
  departments: (orgId: string) => ["org", orgId, "departments"] as const,
  apiKeys: (orgId: string) => ["org", orgId, "api-keys"] as const,
};

function useOrgId(): string | null {
  return useAuthStore((s) => s.organization?.id ?? null);
}

// ── org queries ────────────────────────────────────────────────────────────────

export function useOrg() {
  const orgId = useOrgId();
  return useQuery({
    queryKey: orgKeys.detail(orgId ?? ""),
    queryFn: () => orgsApi.get(orgId!).then((r) => r.data),
    enabled: !!orgId,
  });
}

export function useUpdateOrg() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: OrgUpdatePayload) => orgsApi.update(orgId!, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.detail(orgId!) }),
  });
}

// ── members ────────────────────────────────────────────────────────────────────

export function useMembers() {
  const orgId = useOrgId();
  return useQuery({
    queryKey: orgKeys.members(orgId ?? ""),
    queryFn: () => orgsApi.listMembers(orgId!).then((r) => r.data),
    enabled: !!orgId,
  });
}

export function useUpdateMember() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: MemberUpdatePayload }) =>
      orgsApi.updateMember(orgId!, userId, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.members(orgId!) }),
  });
}

export function useRemoveMember() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => orgsApi.removeMember(orgId!, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.members(orgId!) }),
  });
}

// ── invitations ────────────────────────────────────────────────────────────────

export function useInvitations() {
  const orgId = useOrgId();
  return useQuery({
    queryKey: orgKeys.invitations(orgId ?? ""),
    queryFn: () => orgsApi.listInvitations(orgId!).then((r) => r.data),
    enabled: !!orgId,
  });
}

export function useInviteMember() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: InvitePayload) => orgsApi.invite(orgId!, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.invitations(orgId!) }),
  });
}

export function useRevokeInvitation() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => orgsApi.revokeInvitation(orgId!, invitationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.invitations(orgId!) }),
  });
}

// ── departments ────────────────────────────────────────────────────────────────

export function useDepartments() {
  const orgId = useOrgId();
  return useQuery({
    queryKey: orgKeys.departments(orgId ?? ""),
    queryFn: () => orgsApi.listDepartments(orgId!).then((r) => r.data),
    enabled: !!orgId,
  });
}

export function useCreateDepartment() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DepartmentPayload) =>
      orgsApi.createDepartment(orgId!, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.departments(orgId!) }),
  });
}

export function useDeleteDepartment() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deptId: string) => orgsApi.deleteDepartment(orgId!, deptId),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.departments(orgId!) }),
  });
}

// ── API keys ───────────────────────────────────────────────────────────────────

export function useAPIKeys() {
  const orgId = useOrgId();
  return useQuery({
    queryKey: orgKeys.apiKeys(orgId ?? ""),
    queryFn: () => orgsApi.listAPIKeys(orgId!).then((r) => r.data),
    enabled: !!orgId,
  });
}

export function useCreateAPIKey() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: APIKeyPayload) =>
      orgsApi.createAPIKey(orgId!, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.apiKeys(orgId!) }),
  });
}

export function useRevokeAPIKey() {
  const orgId = useOrgId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => orgsApi.revokeAPIKey(orgId!, keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.apiKeys(orgId!) }),
  });
}
