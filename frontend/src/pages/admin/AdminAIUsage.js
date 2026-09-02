import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AdminAIUsage() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/admin/ai-usage").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="p-4">
          <div className="text-xs text-muted-foreground">Requêtes aujourd'hui</div>
          <div className="text-2xl font-semibold mt-1">{data.total_requests_today}</div>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <div className="text-xs text-muted-foreground">Coût estimé (USD)</div>
          <div className="text-2xl font-semibold mt-1">{data.total_cost_today.toFixed(2)}</div>
        </CardContent></Card>
      </div>
      <Card><CardContent className="p-6 space-y-3">
        <h3 className="font-semibold">Par organisation</h3>
        <div className="divide-y divide-border">
          {(data.organizations || []).map((o) => (
            <div key={o.organization_id} className="py-3 flex items-center justify-between gap-3 text-sm">
              <div className="flex-1 min-w-0">
                <div className="mono text-xs truncate">{o.organization_id}</div>
                <div className="text-xs text-muted-foreground">{o.provider} · {o.model}</div>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <Badge variant="outline">{o.requests_today} req</Badge>
                <Badge variant="outline">${(o.cost_today || 0).toFixed(2)}</Badge>
              </div>
            </div>
          ))}
        </div>
      </CardContent></Card>
    </div>
  );
}
