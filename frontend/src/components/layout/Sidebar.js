import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Home, Bot, Users, Megaphone, BookUser, LineChart, Activity, Plug, ShieldCheck, Settings, LogOut, Sparkles, ShieldAlert } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { cn } from "@/lib/utils";

const items = [
  { to: "/", icon: Home, key: "nav.home", testId: "sidebar-home" },
  { to: "/agents", icon: Bot, key: "nav.agents", testId: "sidebar-agents" },
  { to: "/prospects", icon: Users, key: "nav.prospects", testId: "sidebar-prospects" },
  { to: "/campaigns", icon: Megaphone, key: "nav.campaigns", testId: "sidebar-campaigns" },
  { to: "/contacts", icon: BookUser, key: "nav.contacts", testId: "sidebar-contacts" },
  { to: "/analytics", icon: LineChart, key: "nav.analytics", testId: "sidebar-analytics" },
  { to: "/activity", icon: Activity, key: "nav.activity", testId: "sidebar-activity" },
  { to: "/integrations", icon: Plug, key: "nav.integrations", testId: "sidebar-integrations" },
  { to: "/security", icon: ShieldCheck, key: "nav.security", testId: "sidebar-security" },
  { to: "/settings", icon: Settings, key: "nav.settings", testId: "sidebar-settings" },
];

export default function Sidebar({ mobileOpen, onNavigate }) {
  const { user, logout, t, isSuperAdmin } = useApp();
  const navigate = useNavigate();

  return (
    <aside
      data-testid="app-sidebar"
      className={cn(
        "fixed lg:sticky top-0 left-0 h-screen w-[260px] shrink-0 border-r border-border bg-card z-40 flex-col",
        "transition-transform duration-200",
        mobileOpen ? "flex translate-x-0" : "hidden lg:flex lg:translate-x-0"
      )}
    >
      <div className="px-5 py-5 flex items-center gap-2">
        <div className="w-8 h-8 rounded-md bg-primary text-primary-foreground flex items-center justify-center">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight">Aura Hub</div>
          <div className="text-[11px] text-muted-foreground -mt-0.5">AI Control Center</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {items.map(({ to, icon: Icon, key, testId }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            data-testid={testId}
            onClick={onNavigate}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              isActive
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <Icon className="w-4 h-4" />
            <span>{t(key)}</span>
          </NavLink>
        ))}

        {isSuperAdmin && (
          <div className="mt-4 pt-3 border-t border-border">
            <div className="px-3 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
              Plateforme
            </div>
            <NavLink
              to="/admin"
              data-testid="sidebar-admin"
              onClick={onNavigate}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-foreground hover:bg-accent/50"
              )}
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Administration Aura Hub</span>
            </NavLink>
          </div>
        )}
      </nav>

      <div className="border-t border-border p-3 space-y-1">
        <button
          data-testid="sidebar-profile"
          onClick={() => { navigate("/settings"); onNavigate?.(); }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left hover:bg-accent/50 transition-colors"
        >
          <div className="w-8 h-8 rounded-full bg-secondary text-secondary-foreground flex items-center justify-center text-xs font-semibold">
            {user?.full_name?.[0]?.toUpperCase() || "?"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user?.full_name}</div>
            <div className="text-[11px] text-muted-foreground truncate">{user?.email}</div>
          </div>
        </button>
        <button
          data-testid="sidebar-logout"
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>{t("nav.logout")}</span>
        </button>
      </div>
    </aside>
  );
}
