import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Mail, FileText, TrendingUp, PenLine, Sparkles, Plus, ArrowUpRight, Users, Target, Send, MessageSquare, CalendarCheck, PercentCircle, Bot } from "lucide-react";
import { toast } from "sonner";

const ICONS = { Search, Mail, FileText, TrendingUp, PenLine, Sparkles, Bot };

const KPI_ITEMS = [
  { key: "active_agents", labelKey: "kpi.active_agents", icon: Bot },
  { key: "prospects_found", labelKey: "kpi.prospects_found", icon: Users },
  { key: "qualified", labelKey: "kpi.qualified", icon: Target },
  { key: "messages_prepared", labelKey: "kpi.messages_prepared", icon: MessageSquare },
  { key: "messages_sent", labelKey: "kpi.messages_sent", icon: Send },
  { key: "replies", labelKey: "kpi.replies", icon: ArrowUpRight },
  { key: "meetings", labelKey: "kpi.meetings", icon: CalendarCheck },
  { key: "response_rate", labelKey: "kpi.response_rate", icon: PercentCircle, suffix: "%" },
];

export default function Dashboard() {
  const { user, t } = useApp();
  const navigate = useNavigate();
  const [kpis, setKpis] = useState({});
  const [agents, setAgents] = useState([]);
  const [seeding, setSeeding] = useState(false);

  const load = async () => {
    const [ov, ag] = await Promise.all([
      api.get("/analytics/overview"),
      api.get("/agents"),
    ]);
    setKpis(ov.data.kpis || {});
    setAgents(ag.data || []);
  };
  useEffect(() => { load(); }, []);

  const seedDemo = async () => {
    setSeeding(true);
    try {
      await api.post("/demo/seed");
      toast.success("Données de démonstration ajoutées");
      await load();
    } catch { toast.error("Erreur"); } finally { setSeeding(false); }
  };

  const openAgent = (a) => {
    if (a.key === "prospect_ai") navigate("/prospect-ai");
    else toast.info("Cet agent arrive prochainement");
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            {t("dash.hello")} 👋
            {user?.full_name?.split(" ")[0] && (
              <span className="text-muted-foreground"> {user.full_name.split(" ")[0]}</span>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t("dash.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button data-testid="dashboard-seed-demo" variant="outline" size="sm" onClick={seedDemo} disabled={seeding}>
            <Sparkles className="w-4 h-4 mr-1.5" />{seeding ? "…" : "Ajouter données démo"}
          </Button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {KPI_ITEMS.map(({ key, labelKey, icon: Icon, suffix }) => (
          <Card key={key} data-testid={`kpi-${key}`} className="border-border">
            <CardContent className="p-4">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">{t(labelKey)}</span>
                <Icon className="w-4 h-4" />
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">
                {kpis[key] ?? 0}{suffix || ""}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Agents */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold tracking-tight">{t("dash.my_agents")}</h2>
          <Button data-testid="dashboard-add-agent" size="sm" variant="outline">
            <Plus className="w-4 h-4 mr-1" />{t("dash.add_agent")}
          </Button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((a) => {
            const Icon = ICONS[a.icon] || Bot;
            const available = a.status === "available";
            return (
              <Card key={a.id} data-testid={`agent-card-${a.key}`} className="border-border hover:border-foreground/20 transition-colors cursor-pointer group"
                onClick={() => openAgent(a)}>
                <CardContent className="p-5 flex flex-col h-full">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${available ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant={available ? "default" : "secondary"} className="text-[10px] uppercase tracking-wider">
                      {available ? t("agent.available") : t("agent.coming_soon")}
                    </Badge>
                  </div>
                  <h3 className="font-semibold tracking-tight">{a.name}</h3>
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{a.description}</p>
                  <div className="mt-auto pt-4 flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {available ? (
                        <span className="inline-flex items-center gap-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${a.enabled ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
                          {a.enabled ? t("agent.active") : t("agent.stopped")}
                        </span>
                      ) : t("agent.coming_soon")}
                    </span>
                    <Button data-testid={`agent-open-${a.key}`} size="sm" variant="ghost" className="h-7 text-xs group-hover:bg-accent"
                      disabled={!available}>
                      {t("agent.open")} <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
