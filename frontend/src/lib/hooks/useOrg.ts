import { useAuthStore } from "@/lib/stores/auth.store";

export function useOrg() {
  return useAuthStore((s) => s.organization);
}

export function useOrgId(): string | null {
  return useAuthStore((s) => s.organization?.id ?? null);
}
