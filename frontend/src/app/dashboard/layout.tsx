"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, Upload, List } from "lucide-react";
import { Button } from "@/components/ui/button";
const NAV_ITEMS = [
  { href: "/dashboard/upload", label: "New Upload", icon: Upload },
  { href: "/dashboard/jobs", label: "My Jobs", icon: List },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur-sm dark:bg-neutral-950/80">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link
              href="/dashboard/upload"
              className="flex items-center gap-2 font-semibold"
            >
              <Building2 className="h-5 w-5" />
              <span>ArchGen AI</span>
            </Link>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <Link key={item.href} href={item.href}>
                  <Button
                    variant={pathname.startsWith(item.href) ? "secondary" : "ghost"}
                    size="sm"
                    className="gap-2"
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Button>
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 max-w-7xl mx-auto px-4 py-8 w-full">
        {children}
      </main>
    </div>
  );
}
