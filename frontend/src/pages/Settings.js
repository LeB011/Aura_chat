import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

export default function Settings() {
  const { user, org, reloadOrg, setTheme, setLang } = useApp();
  const [ai, setAi] = useState(null);
  const [profile, setProfile] = useState({ full_name: user?.full_name || "", language: user?.language || "fr", theme: user?.theme || "light" });
  const [orgForm, setOrgForm] = useState({ name: org?.name || "", country: org?.country || "CH", test_mode: !!org?.test_mode });

  useEffect(() => { api.get("/settings/ai").then((r) => setAi(r.data)); }, []);
  useEffect(() => { setOrgForm({ name: org?.name || "", country: org?.country || "CH", test_mode: !!org?.test_mode }); }, [org]);

  const saveProfile = async () => {
    await api.patch("/auth/me", profile);
    setTheme(profile.theme); setLang(profile.language);
    toast.success("Profil enregistré");
  };
  const saveOrg = async () => {
    await api.patch("/settings/organization", orgForm);
    await reloadOrg();
    toast.success("Organisation enregistrée");
  };
  const saveAi = async () => {
    await api.patch("/settings/ai", ai);
    toast.success("Paramètres IA enregistrés");
  };
  const clearDemo = async () => {
    await api.delete("/demo/clear");
    toast.success("Données démo supprimées");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Paramètres</h1>
        <p className="text-sm text-muted-foreground mt-1">Gérez votre profil, votre organisation et vos préférences IA.</p>
      </div>

      <Card><CardContent className="p-6 space-y-4">
        <h3 className="font-semibold">Profil</h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div><Label>Nom</Label><Input value={profile.full_name} onChange={(e) => setProfile({...profile, full_name: e.target.value})} /></div>
          <div><Label>Email</Label><Input value={user?.email} disabled /></div>
          <div><Label>Langue</Label>
            <Select value={profile.language} onValueChange={(v) => setProfile({...profile, language: v})}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="fr">Français</SelectItem><SelectItem value="en">English</SelectItem></SelectContent>
            </Select>
          </div>
          <div><Label>Thème</Label>
            <Select value={profile.theme} onValueChange={(v) => setProfile({...profile, theme: v})}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="light">Clair</SelectItem><SelectItem value="dark">Sombre</SelectItem></SelectContent>
            </Select>
          </div>
        </div>
        <Button data-testid="save-profile" onClick={saveProfile}>Enregistrer</Button>
      </CardContent></Card>

      <Card><CardContent className="p-6 space-y-4">
        <h3 className="font-semibold">Organisation</h3>
        <div className="grid md:grid-cols-3 gap-4">
          <div><Label>Nom</Label><Input value={orgForm.name} onChange={(e) => setOrgForm({...orgForm, name: e.target.value})} /></div>
          <div><Label>Pays ciblé</Label>
            <Select value={orgForm.country} onValueChange={(v) => setOrgForm({...orgForm, country: v})}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="CH">Suisse</SelectItem><SelectItem value="FR">France</SelectItem></SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between border border-border rounded-md px-3">
            <div><Label>Test Mode</Label><div className="text-xs text-muted-foreground">Envois simulés</div></div>
            <Switch checked={orgForm.test_mode} onCheckedChange={(v) => setOrgForm({...orgForm, test_mode: v})} />
          </div>
        </div>
        <div className="flex gap-2">
          <Button data-testid="save-org" onClick={saveOrg}>Enregistrer</Button>
          <Button variant="outline" onClick={clearDemo}>Supprimer données démo</Button>
        </div>
      </CardContent></Card>

      {ai && <Card><CardContent className="p-6 space-y-4">
        <h3 className="font-semibold">Paramètres IA</h3>
        <div className="grid md:grid-cols-3 gap-4">
          <div><Label>Provider</Label>
            <Select value={ai.provider} onValueChange={(v) => setAi({...ai, provider: v})}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="anthropic">Anthropic</SelectItem>
                <SelectItem value="gemini">Gemini</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label>Modèle</Label>
            <Input value={ai.model} onChange={(e) => setAi({...ai, model: e.target.value})} />
          </div>
          <div><Label>Langue par défaut</Label>
            <Select value={ai.language} onValueChange={(v) => setAi({...ai, language: v})}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{["fr","en","de","it","es"].map((s) => <SelectItem key={s} value={s}>{s.toUpperCase()}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-2">
          <Label>Créativité — {Math.round(ai.creativity * 100)}%</Label>
          <Slider value={[ai.creativity * 100]} max={100} step={5}
            onValueChange={(v) => setAi({...ai, creativity: v[0] / 100})} />
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div><Label>Coût max par opération (USD)</Label>
            <Input type="number" step="0.05" value={ai.max_cost_per_operation} onChange={(e) => setAi({...ai, max_cost_per_operation: parseFloat(e.target.value || "0")})} />
          </div>
          <div><Label>Budget quotidien max (USD)</Label>
            <Input type="number" step="1" value={ai.max_daily_usage} onChange={(e) => setAi({...ai, max_daily_usage: parseFloat(e.target.value || "0")})} />
          </div>
        </div>
        <Button data-testid="save-ai" onClick={saveAi}>Enregistrer</Button>
      </CardContent></Card>}
    </div>
  );
}
