import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { authApi, LoginPayload, UserResponse, OrganizationBrief } from "@/lib/api/auth";

interface AuthState {
  user: UserResponse | null;
  organization: OrganizationBrief | null;
  role: string | null;
  isAuthenticated: boolean;
  // Available orgs when the user belongs to multiple — cleared after selection
  pendingOrgs: OrganizationBrief[] | null;

  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  loadMe: () => Promise<void>;
  selectOrg: (orgId: string, password: string) => Promise<void>;
  setUser: (user: UserResponse) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      organization: null,
      role: null,
      isAuthenticated: false,
      pendingOrgs: null,

      login: async (payload: LoginPayload) => {
        const res = await authApi.login(payload);
        const data = res.data;

        if (data.access_token) {
          sessionStorage.setItem("access_token", data.access_token);
        }

        if (data.organizations && !data.organization) {
          // Multiple orgs — user needs to pick one
          set({ pendingOrgs: data.organizations, user: data.user, isAuthenticated: false });
          return;
        }

        set({
          user: data.user,
          organization: data.organization ?? null,
          role: data.role ?? null,
          isAuthenticated: !!data.access_token,
          pendingOrgs: null,
        });
      },

      selectOrg: async (orgId: string, password: string) => {
        const user = get().user;
        if (!user) throw new Error("No pending login session.");
        // Re-login with the chosen org_id
        await get().login({ email: user.email, password, org_id: orgId });
      },

      logout: async () => {
        try {
          await authApi.logout();
        } finally {
          sessionStorage.removeItem("access_token");
          set({ user: null, organization: null, role: null, isAuthenticated: false, pendingOrgs: null });
        }
      },

      loadMe: async () => {
        const res = await authApi.me();
        const { user, organization, role } = res.data;
        set({ user, organization: organization ?? null, role: role ?? null, isAuthenticated: true });
      },

      setUser: (user: UserResponse) => set({ user }),

      clear: () => {
        sessionStorage.removeItem("access_token");
        set({ user: null, organization: null, role: null, isAuthenticated: false, pendingOrgs: null });
      },
    }),
    {
      name: "auth-store",
      storage: createJSONStorage(() => localStorage),
      // Only persist the display-friendly fields — NOT the token (that lives in sessionStorage)
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        role: state.role,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
