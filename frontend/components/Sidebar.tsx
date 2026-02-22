"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  AlertTriangle,
  Camera,
  History,
  Settings,
  LogOut,
  Shield,
  Phone,
  Globe,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout, getUser } from "@/lib/auth";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/cameras", label: "Cameras", icon: Camera },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  return (
    <aside className="w-64 h-screen bg-white border-r border-hospital-border flex flex-col fixed left-0 top-0 z-30">
      {/* Logo */}
      <div className="p-6 border-b border-hospital-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-slate-900">CamGuard</h1>
            <p className="text-xs text-hospital-muted">Caregiver Protection</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-brand-50 text-brand-700 shadow-sm"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Contact Card */}
      <div className="p-4 border-t border-hospital-border space-y-3">
        <div className="card-compact space-y-2">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-hospital-muted" />
            <span className="text-xs font-medium text-slate-700">{user?.name || "Caregiver"}</span>
          </div>
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-hospital-muted" />
            <span className="text-xs text-hospital-muted">Primary Contact</span>
          </div>
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-hospital-muted" />
            <span className="text-xs text-hospital-muted">English</span>
          </div>
        </div>

        <button
          onClick={() => {
            logout();
            router.push("/login");
          }}
          className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
