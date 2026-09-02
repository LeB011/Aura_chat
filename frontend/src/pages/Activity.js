import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Info, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

const ICONS = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: XCircle };
const COLORS = { info: "text-muted-foreground", success: "text-emerald-500", warning: "text-amber-500", error: "text-destructive" };

export default function ActivityPage() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/activities").then((r) => setItems(r.data)); }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Activité</h1>
        <p className="text-sm text-muted-foreground mt-1">Journal complet de toutes les actions de vos agents.</p>
      </div>
      <Card>
        <CardContent className="p-0 divide-y divide-border">
          {items.length === 0 && <div className="p-10 text-center text-muted-foreground text-sm">Aucune activité pour l'instant.</div>}
          {items.map((a) => {
            const Icon = ICONS[a.status] || Info;
            const d = new Date(a.created_at);
            return (
              <div key={a.id} className="p-4 flex items-start gap-3">
                <div className={`mt-0.5 ${COLORS[a.status] || "text-muted-foreground"}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{a.action}</div>
                  {a.target && <div className="text-xs text-muted-foreground">{a.target}{a.result ? ` — ${a.result}` : ""}</div>}
                </div>
                <div className="text-xs text-muted-foreground mono shrink-0">
                  {d.toLocaleString()}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
