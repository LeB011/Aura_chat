import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function Login() {
  const { login, register, t } = useApp();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "", organization_name: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register(form);
      }
      toast.success("Bienvenue sur Aura Hub");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left visual */}
      <div className="hidden lg:flex flex-col justify-between p-10 border-r border-border bg-card relative overflow-hidden">
        <div className="dot-pattern absolute inset-0 opacity-40" />
        <div className="relative z-10 flex items-center gap-2">
          <div className="w-9 h-9 rounded-md bg-primary text-primary-foreground flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="text-lg font-semibold tracking-tight">Aura Hub</div>
        </div>
        <div className="relative z-10 max-w-md">
          <h1 className="text-4xl font-semibold tracking-tight leading-tight">
            Le centre de contrôle de vos agents IA.
          </h1>
          <p className="mt-4 text-sm text-muted-foreground">
            Trouvez, qualifiez et engagez vos prospects B2B en gardant l'humain dans la boucle.
          </p>
          <div className="mt-8 space-y-2 text-sm text-muted-foreground">
            <div>— Prospect AI : recherche & qualification IA</div>
            <div>— Human-in-the-loop, Test Mode, Kill switch</div>
            <div>— Extensible : ajoutez vos propres agents</div>
          </div>
        </div>
        <div className="relative z-10 text-xs text-muted-foreground">
          © {new Date().getFullYear()} Aura Hub — Premium AI Suite
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 lg:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-md bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="font-semibold">Aura Hub</div>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">
            {mode === "login" ? t("auth.login") : t("auth.register")}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {mode === "login" ? "Accédez à votre espace." : "Créez votre organisation en 30 secondes."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "register" && (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="full_name">{t("auth.name")}</Label>
                  <Input data-testid="auth-name" id="full_name" value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="organization_name">{t("auth.company")}</Label>
                  <Input data-testid="auth-company" id="organization_name" value={form.organization_name}
                    onChange={(e) => setForm({ ...form, organization_name: e.target.value })} required />
                </div>
              </>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">{t("auth.email")}</Label>
              <Input data-testid="auth-email" id="email" type="email" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">{t("auth.password")}</Label>
              <Input data-testid="auth-password" id="password" type="password" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} />
            </div>
            <Button data-testid="auth-submit" type="submit" className="w-full" disabled={busy}>
              {busy ? "..." : (mode === "login" ? t("auth.login") : t("auth.register"))}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            {mode === "login" ? t("auth.no_account") : t("auth.have_account")}
            <button
              data-testid="auth-switch"
              type="button"
              className="ml-2 underline underline-offset-2 hover:text-foreground"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? t("auth.register") : t("auth.login")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
