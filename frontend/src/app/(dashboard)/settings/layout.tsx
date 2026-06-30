"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePermission } from "@/lib/hooks/usePermission";

const navItems = [
  { href: "/settings/profile", label: "Profile", minRole: "viewer" },
  { href: "/settings/organization", label: "Organization", minRole: "viewer" },
  { href: "/settings/members", label: "Members", minRole: "viewer" },
  { href: "/settings/departments", label: "Departments", minRole: "viewer" },
  { href: "/settings/api-keys", label: "API Keys", minRole: "admin" },
  { href: "/settings/integrations", label: "Integrations", minRole: "admin" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 border-r bg-gray-50 pt-8 px-4 flex-shrink-0">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4 px-2">
          Settings
        </h2>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <NavItem key={item.href} {...item} active={pathname === item.href} />
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}

function NavItem({
  href,
  label,
  minRole,
  active,
}: {
  href: string;
  label: string;
  minRole: string;
  active: boolean;
}) {
  const allowed = usePermission(minRole);
  if (!allowed) return null;

  return (
    <Link
      href={href}
      className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
        active
          ? "bg-blue-50 text-blue-700 font-medium"
          : "text-gray-700 hover:bg-gray-100"
      }`}
    >
      {label}
    </Link>
  );
}
