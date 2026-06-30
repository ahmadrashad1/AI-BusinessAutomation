import { useAuthStore } from "@/lib/stores/auth.store";

const ROLE_RANK: Record<string, number> = {
  owner: 6,
  admin: 5,
  manager: 4,
  analyst: 3,
  employee: 2,
  viewer: 1,
};

export function usePermission(minRole: string): boolean {
  const role = useAuthStore((s) => s.role);
  if (!role) return false;
  return (ROLE_RANK[role] ?? 0) >= (ROLE_RANK[minRole] ?? 0);
}

export function useRole(): string | null {
  return useAuthStore((s) => s.role);
}
