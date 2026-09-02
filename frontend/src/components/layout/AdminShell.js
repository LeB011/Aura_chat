import React from "react";
import { Outlet, Navigate, NavLink } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { LayoutDashboard, Building2, Users, Bot, Cpu, ClipboardList, SlidersHorizontal, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { to: "/admin", end: true, icon: LayoutDashboard, label: "Vue générale" },
  { to: "/admin/organizations", icon: Building2, label: "Organisations" },
  { to: "/admin/users", icon: Users, label: "Utilisateurs" },
  { to: "/admin/agents", icon: Bot, label: "Agents" },
  { to: "/admin/ai-usage", icon: Cpu, label: "Usage IA" },
  { to: "/admin/logs", icon: ClipboardList, label: "Logs plateforme" },
  { to: "/admin/platform-settings", icon: SlidersHorizontal, label: "Configuration" },
];

export default function AdminShell() {
  const { user, loading } = useApp();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "superadmin") return <Navigate to="/" replace />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
            <NavLink to="/" className="hover:text-foreground flex items-center gap-1">
              <ArrowLeft className="w-3 h-3" /> Retour espace client
            </NavLink>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Administration Aura Hub</h1>
          <p className="text-sm text-muted-foreground">Gestion de la plateforme — accès superadmin uniquement.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-border pb-1 -mx-1 overflow-x-auto">
        {items.map(({ to, end, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            data-testid={`admin-nav-${to.split("/").pop() || "overview"}`}
            className={({ isActive }) => cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm shrink-0 transition-colors",
              isActive
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
            )}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  );
}
