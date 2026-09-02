import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, ShieldCheck, StopCircle } from "lucide-react";
import { toast } from "sonner";

const TOGGLES = [
  ["human_approval_required", "Validation humaine obligatoire", "Exiger une validation manuelle avant tout envoi."],
  ["duplicate_protection", "Protection anti-doublon", "Empêcher d'envoyer plusieurs fois au même contact."],
  ["existing_customer_exclusion", "Exclusion clients existants", "Ne pas prospecter les clients déjà enregistrés."],
  ["dnc_list_enabled", "Liste 'ne pas contacter'", "Respecter la liste DNC de l'organisation."],
  ["unsubscribe_protection", "Protection opt-out", "Bloquer tout contact désinscrit."],
  ["invalid_email_protection", "Emails invalides", "Filtrer automatiquement les emails malformés."],
  ["generic_email_warning", "Alerte emails génériques", "Marquer info@, contact@, office@ comme sensibles."],
  ["personal_email_warning", "Alerte emails personnels", "Signaler Gmail, Hotmail, Bluewin, etc."],
  ["require_professional_relevance", "Pertinence professionnelle requise", "L'IA doit justifier chaque prospect."],
  ["ai_hallucination_protection", "Protection anti-hallucination IA", "Marquer les infos non vérifiées comme hypothèses."],
  ["sensitive_industry_protection", "Secteurs sensibles", "Alerte pour secteurs réglementés."],
  ["compliance_review_required", "Revue de conformité", "Bloque en cas de risque et demande validation."],
];

export default function Security() {
  const [s, setS] = useState(null);
  const load = async () => setS((await api.get("/security")).data);
  useEffect(() => { load(); }, []);

  const update = async (patch) => {
    const { data } = await api.patch("/security", patch);
    setS(data);
    toast.success("Enregistré");
  };

  if (!s) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-6 h-6" /> Security Center
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Contrôlez précisément ce que vos agents ont le droit de faire.</p>
        </div>
        <Button
          data-testid="kill-switch-btn"
          variant={s.kill_switch_active ? "outline" : "destructive"}
          onClick={() => api.post("/security/kill-switch", { active: !s.kill_switch_active }).then(load)}
          className="w-full md:w-auto"
        >
          <StopCircle className="w-4 h-4 mr-1.5" />
          {s.kill_switch_active ? "Réactiver les agents" : "Kill switch : arrêter tout"}
        </Button>
      </div>

      {s.kill_switch_active && (
        <div className="p-4 rounded-md border border-destructive/40 bg-destructive/5 text-destructive flex items-center gap-2 text-sm">
          <AlertTriangle className="w-4 h-4" /> Kill switch actif — toutes les actions automatisées sont bloquées.
        </div>
      )}

      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="font-semibold">Protections principales</h3>
          <div className="divide-y divide-border">
            {TOGGLES.map(([key, label, desc]) => (
              <div key={key} className="flex items-start justify-between py-3">
                <div className="flex-1 pr-4">
                  <div className="text-sm font-medium">{label}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{desc}</div>
                </div>
                <Switch data-testid={`sec-${key}`} checked={!!s[key]} onCheckedChange={(v) => update({ [key]: v })} />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="font-semibold">Limites & délais</h3>
          <div className="grid md:grid-cols-3 gap-4">
            <div><Label>Limite envois par jour</Label>
              <Input type="number" value={s.daily_sending_limit} onChange={(e) => setS({...s, daily_sending_limit: parseInt(e.target.value || "0")})} onBlur={() => update({ daily_sending_limit: s.daily_sending_limit })} />
            </div>
            <div><Label>Limite envois par heure</Label>
              <Input type="number" value={s.hourly_sending_limit} onChange={(e) => setS({...s, hourly_sending_limit: parseInt(e.target.value || "0")})} onBlur={() => update({ hourly_sending_limit: s.hourly_sending_limit })} />
            </div>
            <div><Label>Délai entre messages (min.)</Label>
              <Input type="number" value={s.delay_between_messages_minutes} onChange={(e) => setS({...s, delay_between_messages_minutes: parseInt(e.target.value || "0")})} onBlur={() => update({ delay_between_messages_minutes: s.delay_between_messages_minutes })} />
            </div>
            <div><Label>Seuil de confiance IA (%)</Label>
              <Input type="number" value={s.confidence_threshold} onChange={(e) => setS({...s, confidence_threshold: parseInt(e.target.value || "0")})} onBlur={() => update({ confidence_threshold: s.confidence_threshold })} />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-2">
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-500" /><h3 className="font-semibold">Conformité</h3></div>
          <p className="text-sm text-muted-foreground">
            Les règles de prospection peuvent varier selon le pays, le canal et la situation. L'utilisateur reste responsable de vérifier que son utilisation respecte la réglementation applicable.
          </p>
          <Badge variant="outline" className="mt-2 text-[10px]">Suisse par défaut</Badge>
        </CardContent>
      </Card>
    </div>
  );
}
