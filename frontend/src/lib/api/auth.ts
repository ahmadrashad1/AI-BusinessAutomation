import apiClient from "./client";

// ── request types ──────────────────────────────────────────────────────────

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  invite_token?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  org_id?: string;
}

// ── response types ─────────────────────────────────────────────────────────

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  is_verified: boolean;
  created_at: string;
}

export interface OrganizationBrief {
  id: string;
  name: string;
  slug: string;
  plan: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
  organization?: OrganizationBrief;
  role?: string;
  organizations?: OrganizationBrief[]; // org-picker: user has multiple orgs
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface MeResponse {
  user: UserResponse;
  organization?: OrganizationBrief;
  role?: string;
}

// ── API calls ──────────────────────────────────────────────────────────────

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<UserResponse>("/auth/register", payload),

  login: (payload: LoginPayload) =>
    apiClient.post<LoginResponse>("/auth/login", payload),

  logout: () =>
    apiClient.post<void>("/auth/logout"),

  refresh: () =>
    apiClient.post<RefreshResponse>("/auth/refresh"),

  me: () =>
    apiClient.get<MeResponse>("/auth/me"),

  verifyEmail: (token: string) =>
    apiClient.post<{ message: string }>("/auth/verify-email", { token }),

  resendVerification: (email: string) =>
    apiClient.post<{ message: string }>("/auth/resend-verification", { email }),

  forgotPassword: (email: string) =>
    apiClient.post<{ message: string }>("/auth/forgot-password", { email }),

  resetPassword: (token: string, new_password: string) =>
    apiClient.post<{ message: string }>("/auth/reset-password", { token, new_password }),
};
