import apiClient from "./client";

// ── types ──────────────────────────────────────────────────────────────────────

export interface OrgResponse {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  settings: Record<string, unknown>;
  storage_used_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface MemberResponse {
  id: string;
  organization_id: string;
  user_id: string;
  role: string;
  department_id: string | null;
  joined_at: string;
}

export interface DepartmentResponse {
  id: string;
  organization_id: string;
  name: string;
  created_at: string;
}

export interface InvitationResponse {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
}

export interface APIKeyResponse {
  id: string;
  organization_id: string;
  label: string;
  key_prefix: string;
  scopes: string[];
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface APIKeyCreatedResponse extends APIKeyResponse {
  key: string;
}

// ── request payloads ───────────────────────────────────────────────────────────

export interface OrgCreatePayload {
  name: string;
  slug?: string;
}

export interface OrgUpdatePayload {
  name?: string;
  plan?: string;
  is_active?: boolean;
  settings?: Record<string, unknown>;
}

export interface MemberUpdatePayload {
  role: string;
  department_id?: string;
}

export interface InvitePayload {
  email: string;
  role: string;
}

export interface DepartmentPayload {
  name: string;
}

export interface APIKeyPayload {
  label: string;
  scopes: string[];
  expires_at?: string;
}

// ── API calls ──────────────────────────────────────────────────────────────────

export const orgsApi = {
  // Organization
  create: (payload: OrgCreatePayload) =>
    apiClient.post<OrgResponse>("/orgs", payload),

  get: (orgId: string) =>
    apiClient.get<OrgResponse>(`/orgs/${orgId}`),

  update: (orgId: string, payload: OrgUpdatePayload) =>
    apiClient.patch<OrgResponse>(`/orgs/${orgId}`, payload),

  delete: (orgId: string, confirmation: string) =>
    apiClient.delete<void>(`/orgs/${orgId}`, { data: { confirmation } }),

  transferOwnership: (orgId: string, newOwnerUserId: string) =>
    apiClient.post<OrgResponse>(`/orgs/${orgId}/transfer-ownership`, {
      new_owner_user_id: newOwnerUserId,
    }),

  // Members
  listMembers: (orgId: string) =>
    apiClient.get<MemberResponse[]>(`/orgs/${orgId}/members`),

  updateMember: (orgId: string, userId: string, payload: MemberUpdatePayload) =>
    apiClient.patch<MemberResponse>(`/orgs/${orgId}/members/${userId}`, payload),

  removeMember: (orgId: string, userId: string) =>
    apiClient.delete<void>(`/orgs/${orgId}/members/${userId}`),

  // Invitations
  listInvitations: (orgId: string) =>
    apiClient.get<InvitationResponse[]>(`/orgs/${orgId}/invitations`),

  invite: (orgId: string, payload: InvitePayload) =>
    apiClient.post<InvitationResponse>(`/orgs/${orgId}/invitations`, payload),

  revokeInvitation: (orgId: string, invitationId: string) =>
    apiClient.delete<void>(`/orgs/${orgId}/invitations/${invitationId}`),

  acceptInvitation: (token: string) =>
    apiClient.post<{ organization: OrgResponse; role: string }>("/invitations/accept", { token }),

  // Departments
  listDepartments: (orgId: string) =>
    apiClient.get<DepartmentResponse[]>(`/orgs/${orgId}/departments`),

  createDepartment: (orgId: string, payload: DepartmentPayload) =>
    apiClient.post<DepartmentResponse>(`/orgs/${orgId}/departments`, payload),

  updateDepartment: (orgId: string, deptId: string, payload: DepartmentPayload) =>
    apiClient.patch<DepartmentResponse>(`/orgs/${orgId}/departments/${deptId}`, payload),

  deleteDepartment: (orgId: string, deptId: string) =>
    apiClient.delete<void>(`/orgs/${orgId}/departments/${deptId}`),

  // API Keys
  listAPIKeys: (orgId: string) =>
    apiClient.get<APIKeyResponse[]>(`/orgs/${orgId}/api-keys`),

  createAPIKey: (orgId: string, payload: APIKeyPayload) =>
    apiClient.post<APIKeyCreatedResponse>(`/orgs/${orgId}/api-keys`, payload),

  revokeAPIKey: (orgId: string, keyId: string) =>
    apiClient.delete<void>(`/orgs/${orgId}/api-keys/${keyId}`),
};
