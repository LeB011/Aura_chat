import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import api from "@/lib/api";
import { t as translate } from "@/lib/i18n";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(localStorage.getItem("aura_theme") || "light");
  const [lang, setLang] = useState(localStorage.getItem("aura_lang") || "fr");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("aura_theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("aura_lang", lang);
  }, [lang]);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("aura_token");
    if (!token) { setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      if (data.language) setLang(data.language);
      if (data.theme) setTheme(data.theme);
      const orgResp = await api.get("/settings/organization");
      setOrg(orgResp.data);
    } catch {
      localStorage.removeItem("aura_token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("aura_token", data.access_token);
    setUser(data.user);
    if (data.user.language) setLang(data.user.language);
    if (data.user.theme) setTheme(data.user.theme);
    const orgResp = await api.get("/settings/organization");
    setOrg(orgResp.data);
    return data.user;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.setItem("aura_token", data.access_token);
    setUser(data.user);
    const orgResp = await api.get("/settings/organization");
    setOrg(orgResp.data);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("aura_token");
    setUser(null);
    setOrg(null);
    window.location.href = "/login";
  };

  const toggleTestMode = async () => {
    const next = !(org?.test_mode);
    const { data } = await api.patch("/settings/organization", { test_mode: next });
    setOrg(data);
    return data;
  };

  const t = useCallback((k) => translate(lang, k), [lang]);

  const value = useMemo(() => ({
    user, org, setOrg, loading, theme, setTheme, lang, setLang, t,
    login, register, logout, toggleTestMode,
    isSuperAdmin: user?.role === "superadmin",
    reloadOrg: async () => {
      const orgResp = await api.get("/settings/organization"); setOrg(orgResp.data);
    }
  }), [user, org, loading, theme, lang, t]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside provider");
  return ctx;
}
