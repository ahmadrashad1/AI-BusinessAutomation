import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  withCredentials: true, // send HttpOnly refresh_token cookie automatically
  headers: { "Content-Type": "application/json" },
});

// ── request interceptor: inject access token ──────────────────────────────

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    const token = sessionStorage.getItem("access_token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return config;
});

// ── response interceptor: handle 401 → refresh → retry ───────────────────

let _refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await axios.post<{ access_token: string }>(
      `${API_BASE}/api/v1/auth/refresh`,
      {},
      { withCredentials: true }
    );
    const newToken = res.data.access_token;
    sessionStorage.setItem("access_token", newToken);
    return newToken;
  } catch {
    sessionStorage.removeItem("access_token");
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

    // Only retry once, only for 401, and not for auth endpoints themselves
    if (
      error.response?.status === 401 &&
      !original._retried &&
      !original.url?.includes("/auth/refresh") &&
      !original.url?.includes("/auth/login")
    ) {
      original._retried = true;

      // Serialise concurrent refresh calls
      if (!_refreshing) {
        _refreshing = refreshAccessToken().finally(() => {
          _refreshing = null;
        });
      }

      const newToken = await _refreshing;
      if (newToken) {
        original.headers["Authorization"] = `Bearer ${newToken}`;
        return apiClient(original);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
