import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppProvider } from "@/context/AppContext";
import { Toaster } from "sonner";
import AppShell from "@/components/layout/AppShell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ProspectAI from "@/pages/ProspectAI";
import Prospects from "@/pages/Prospects";
import ProspectDetail from "@/pages/ProspectDetail";
import Campaigns from "@/pages/Campaigns";
import Analytics from "@/pages/Analytics";
import ActivityPage from "@/pages/Activity";
import Integrations from "@/pages/Integrations";
import Security from "@/pages/Security";
import Settings from "@/pages/Settings";
import Agents from "@/pages/Agents";
import AdminShell from "@/components/layout/AdminShell";
import AdminOverview from "@/pages/admin/AdminOverview";
import AdminOrganizations from "@/pages/admin/AdminOrganizations";
import AdminUsers from "@/pages/admin/AdminUsers";
import AdminAgents from "@/pages/admin/AdminAgents";
import AdminPlatformSettings from "@/pages/admin/AdminPlatformSettings";
import AdminLogs from "@/pages/admin/AdminLogs";
import AdminAIUsage from "@/pages/admin/AdminAIUsage";
import "@/App.css";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Toaster position="bottom-right" theme="system" richColors />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="agents" element={<Agents />} />
            <Route path="prospect-ai" element={<ProspectAI />} />
            <Route path="prospects" element={<Prospects />} />
            <Route path="prospects/:id" element={<ProspectDetail />} />
            <Route path="campaigns" element={<Campaigns />} />
            <Route path="contacts" element={<Prospects />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="integrations" element={<Integrations />} />
            <Route path="security" element={<Security />} />
            <Route path="settings" element={<Settings />} />
            <Route path="admin" element={<AdminShell />}>
              <Route index element={<AdminOverview />} />
              <Route path="organizations" element={<AdminOrganizations />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="agents" element={<AdminAgents />} />
              <Route path="ai-usage" element={<AdminAIUsage />} />
              <Route path="logs" element={<AdminLogs />} />
              <Route path="platform-settings" element={<AdminPlatformSettings />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
