"use client";

import { usePermission } from "@/lib/hooks/usePermission";

interface PermissionGateProps {
  minRole: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function PermissionGate({ minRole, children, fallback = null }: PermissionGateProps) {
  const allowed = usePermission(minRole);
  return allowed ? <>{children}</> : <>{fallback}</>;
}
