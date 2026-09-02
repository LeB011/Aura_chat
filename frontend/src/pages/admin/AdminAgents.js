import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const STATUSES = ["available", "beta", "coming_soon", "disabled"];

export default function AdminAgents() {
  const [agents, setAgents] = useState([]);
  const load = async () => setAgents((await api.get("/admin/agents")).data);
  useEffect(() => { load(); }, []);

  const changeStatus = async (key, status) => {
    await api.patch(`/admin/agents/${key}`, { status });
    toast.success("Statut agent mis à jour");
    load();
  };

  return (
    <Card>
      <CardContent className="p-6">
        <h3 className="font-semibold mb-4">Catalogue d'agents (toutes organisations)</h3>
        <div className="divide-y divide-border">
          {agents.map((a) => (
            <div key={a.key} data-testid={`admin-agent-${a.key}`} className="py-3 flex flex-col md:flex-row md:items-center gap-3 md:gap-4">
              <div className="flex-1 min-w-0">
                <div className="font-medium">{a.name}</div>
                <div className="text-xs text-muted-foreground mono">{a.key}</div>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <Badge variant="outline" className="text-[10px]">
                  {a.enabled_count}/{a.installations} actifs
                </Badge>
                <Select value={a.status} onValueChange={(v) => changeStatus(a.key, v)}>
                  <SelectTrigger className="h-8 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
