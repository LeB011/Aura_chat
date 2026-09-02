import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Search, Mail, FileText, TrendingUp, PenLine, Sparkles, Bot } from "lucide-react";
import { toast } from "sonner";

const ICONS = { Search, Mail, FileText, TrendingUp, PenLine, Sparkles, Bot };

export default function Agents() {
  const { t } = useApp();
  const nav = useNavigate();
  const [agents, setAgents] = useState([]);
  const load = async () => setAgents((await api.get("/agents")).data);
  useEffect(() => { load(); }, []);

  const toggle = async (a) => {
    if (a.status !== "available") return toast.info("Cet agent arrive prochainement");
    await api.patch(`/agents/${a.key}`, { enabled: !a.enabled });
    load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mes Agents</h1>
        <p className="text-sm text-muted-foreground mt-1">Activez ou désactivez chaque agent selon vos besoins.</p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((a) => {
          const Icon = ICONS[a.icon] || Bot;
          const available = a.status === "available";
          return (
            <Card key={a.id} data-testid={`agents-card-${a.key}`} className="hover:border-foreground/20 transition-colors">
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${available ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <Badge variant={available ? "default" : "secondary"} className="text-[10px] uppercase">{available ? t("agent.available") : t("agent.coming_soon")}</Badge>
                </div>
                <h3 className="font-semibold">{a.name}</h3>
                <p className="text-sm text-muted-foreground mt-1">{a.description}</p>
                <div className="mt-4 flex items-center justify-between">
                  <Switch checked={!!a.enabled} disabled={!available} onCheckedChange={() => toggle(a)} />
                  {available && (
                    <button onClick={() => nav("/prospect-ai")} className="text-sm underline underline-offset-2 hover:no-underline">
                      Ouvrir
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
