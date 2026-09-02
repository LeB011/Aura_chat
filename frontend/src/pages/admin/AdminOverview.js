import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Building2, Users, Bot, Send, MessageSquare, AlertCircle, Cpu, PieChart } from "lucide-react";

const KPIS = [
  { key: "total_organizations", label: "Organisations", icon: Building2 },
  { key: "active_organizations", label: "Actives", icon: Building2 },
  { key: "suspended_organizations", label: "Suspendues", icon: AlertCircle },
  { key: "total_users", label: "Utilisateurs", icon: Users },
  { key: "total_prospects", label: "Prospects", icon: Users },
  { key: "prospects_today", label: "Prospects aujourd'hui", icon: PieChart },
  { key: "total_campaigns", label: "Campagnes", icon: Bot },
  { key: "active_agents", label: "Agents actifs", icon: Bot },
  { key: "messages_prepared", label: "Messages préparés", icon: MessageSquare },
  { key: "messages_sent", label: "Messages envoyés", icon: Send },
  { key: "errors_recent", label: "Erreurs 24h", icon: AlertCircle },
  { key: "ai_operations_estimated", label: "Opérations IA (est.)", icon: Cpu },
];

export default function AdminOverview() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/admin/overview").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {KPIS.map(({ key, label, icon: Icon }) => (
          <Card key={key} data-testid={`admin-kpi-${key}`} className="border-border">
            <CardContent className="p-4">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">{label}</span>
                <Icon className="w-4 h-4" />
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">{data[key] ?? 0}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-6">
          <h3 className="font-semibold mb-3">Activité récente</h3>
          <div className="divide-y divide-border">
            {(data.recent_activity || []).length === 0 && (
              <div className="text-sm text-muted-foreground py-4">Aucune activité récente.</div>
            )}
            {(data.recent_activity || []).map((a) => (
              <div key={a.id} className="py-2.5 text-sm flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{a.action}</div>
                  {a.target && <div className="text-xs text-muted-foreground">{a.target}</div>}
                </div>
                <div className="text-xs text-muted-foreground mono shrink-0">
                  {new Date(a.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
