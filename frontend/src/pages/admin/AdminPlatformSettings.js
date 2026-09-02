import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

export default function AdminPlatformSettings() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/admin/platform-settings").then((r) => setS(r.data)); }, []);

  const [cleanup, setCleanup] = useState(null);
  const previewCleanup = async () => {
    const { data } = await api.get("/admin/test-data/cleanup-preview");
    setCleanup(data);
  };
  const runCleanup = async () => {
    if (!window.confirm(`Supprimer uniquement les données TEST détectées ? ${cleanup?.organizations || 0} organisations seront supprimées.`)) return;
    const { data } = await api.post("/admin/test-data/cleanup", { confirm: true });
    toast.success(`Nettoyage terminé : ${data.deleted?.organizations || 0} organisation(s) supprimée(s)`);
    setCleanup(null);
  };

  const save = async () => {
    const { data } = await api.patch("/admin/platform-settings", {
      default_ai_provider: s.default_ai_provider,
      default_ai_model: s.default_ai_model,
      allowed_ai_models: s.allowed_ai_models,
      global_ai_daily_budget: parseFloat(s.global_ai_daily_budget),
      default_test_mode: !!s.default_test_mode,
      maintenance_mode: !!s.maintenance_mode,
      enabled_integrations: s.enabled_integrations,
    });
    setS(data);
    toast.success("Configuration plateforme enregistrée");
  };

  if (!s) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  return (
    <Card>
      <CardContent className="p-6 space-y-6">
        <h3 className="font-semibold">Configuration IA par défaut</h3>
        <div className="grid md:grid-cols-3 gap-4">
          <div><Label>Provider par défaut</Label>
            <Input value={s.default_ai_provider} onChange={(e) => setS({...s, default_ai_provider: e.target.value})} />
          </div>
          <div><Label>Modèle par défaut</Label>
            <Input value={s.default_ai_model} onChange={(e) => setS({...s, default_ai_model: e.target.value})} />
          </div>
          <div><Label>Budget IA quotidien global (USD)</Label>
            <Input type="number" step="1" value={s.global_ai_daily_budget}
              onChange={(e) => setS({...s, global_ai_daily_budget: e.target.value})} />
          </div>
        </div>
        <div>
          <Label>Modèles autorisés (séparés par ,)</Label>
          <Input value={(s.allowed_ai_models || []).join(", ")}
            onChange={(e) => setS({...s, allowed_ai_models: e.target.value.split(",").map((x) => x.trim()).filter(Boolean)})} />
        </div>

        <div className="border-t border-border pt-4 grid md:grid-cols-2 gap-4">
          <div className="flex items-center justify-between border border-border rounded-md px-3 py-2">
            <div><Label>Test Mode par défaut</Label>
              <div className="text-xs text-muted-foreground">Nouvelles orgs démarrent en Test Mode</div></div>
            <Switch checked={!!s.default_test_mode} onCheckedChange={(v) => setS({...s, default_test_mode: v})} />
          </div>
          <div className="flex items-center justify-between border border-border rounded-md px-3 py-2">
            <div><Label>Mode maintenance</Label>
              <div className="text-xs text-muted-foreground">Coupe temporairement l'accès à la plateforme</div></div>
            <Switch checked={!!s.maintenance_mode} onCheckedChange={(v) => setS({...s, maintenance_mode: v})} />
          </div>
        </div>

        <div>
          <Label>Intégrations activées (clés séparées par ,)</Label>
          <Input value={(s.enabled_integrations || []).join(", ")}
            onChange={(e) => setS({...s, enabled_integrations: e.target.value.split(",").map((x) => x.trim()).filter(Boolean)})} />
        </div>

        <div className="border-t pt-4 space-y-3">
          <div>
            <Label>Nettoyage des données TEST</Label>
            <div className="text-xs text-muted-foreground">Détecte les données explicitement TEST et les comptes de tests automatisés @example.com. Votre organisation courante est protégée.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={previewCleanup}>Prévisualiser</Button>
            {cleanup && <Button variant="destructive" onClick={runCleanup} disabled={!cleanup.organizations}>Nettoyer les données TEST</Button>}
          </div>
          {cleanup && <div className="text-sm rounded-md border p-3">{cleanup.organizations} organisations · {cleanup.users} utilisateurs · {cleanup.campaigns} campagnes · {cleanup.prospects} prospects · {cleanup.messages} messages</div>}
        </div>

        <Button data-testid="admin-platform-save" onClick={save}>Enregistrer</Button>
      </CardContent>
    </Card>
  );
}
