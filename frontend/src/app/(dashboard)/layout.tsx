"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth.store";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const loadMe = useAuthStore((s) => s.loadMe);

  useEffect(() => {
    if (!isAuthenticated) {
      // Try to restore session from the refresh token cookie
      loadMe().catch(() => {
        router.replace("/login");
      });
    }
  }, [isAuthenticated, loadMe, router]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading…</div>
      </div>
    );
  }

  return <>{children}</>;
}
