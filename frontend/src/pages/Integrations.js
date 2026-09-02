import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bot, Sheet, Mail, Send, Map, Database, Workflow, Zap, Webhook, FileSpreadsheet, Code } from "lucide-react";
import { toast } from "sonner";

const ICONS = { Bot, Sheet, Mail, Send, Map, Database, Workflow, Zap, Webhook, FileSpreadsheet, Code };

export default function Integrations() {
  const [items, setItems] = useState([]);
  const load = async () => setItems((await api.get("/integrations")).data);
  useEffect(() => { load(); }, []);

  const toggle = async (i) => {
    if (i.managed_server_side) {
      try {
        const { data } = await api.post(`/integrations/${i.key}/validate`);
        if (data.ok) toast.success(`${i.name} est correctement configuré côté serveur`);
        else toast.error(data.error || `${i.name} n'est pas configuré`);
      } catch (e) { toast.error(e?.response?.data?.detail || "Validation impossible"); }
      load(); return;
    }
    toast.info("Cette intégration n'est pas encore activée dans V2.1.");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Intégrations</h1>
        <p className="text-sm text-muted-foreground mt-1">Connectez vos outils préférés. Architecture provider prête pour la V2.</p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((i) => {
          const Icon = ICONS[i.icon] || Bot;
          return (
            <Card key={i.key} data-testid={`integration-${i.key}`} className="hover:border-foreground/20 transition-colors">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 rounded-md bg-secondary flex items-center justify-center">
                    <Icon className="w-5 h-5 text-secondary-foreground" />
                  </div>
                  <Badge variant={i.connected ? "default" : "outline"} className="text-[10px]">{i.status === "error" ? "Erreur" : i.connected ? "Connecté" : i.managed_server_side ? "Non configuré" : "Bientôt disponible"}</Badge>
                </div>
                <div className="mt-3 font-medium">{i.name}</div>
                <div className="mt-4">
                  <Button size="sm" variant={i.connected ? "outline" : "default"} onClick={() => toggle(i)}>{i.managed_server_side ? "Vérifier" : "Voir l'état"}</Button>
                  {i.key === "google_places" && !i.connected && <p className="text-xs text-muted-foreground mt-2">Ajoutez GOOGLE_PLACES_API_KEY dans les variables d'environnement du backend.</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
