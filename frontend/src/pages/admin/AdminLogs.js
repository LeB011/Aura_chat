import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Info, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

const ICONS = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: XCircle };
const COLORS = { info: "text-muted-foreground", success: "text-emerald-500", warning: "text-amber-500", error: "text-destructive" };

export default function AdminLogs() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/logs", { params: { limit: 300 } }).then((r) => setItems(r.data)); }, []);

  return (
    <Card>
      <CardContent className="p-0 divide-y divide-border">
        {items.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">Aucun log.</div>}
        {items.map((a) => {
          const Icon = ICONS[a.status] || Info;
          return (
            <div key={a.id} className="p-4 flex items-start gap-3">
              <div className={`mt-0.5 ${COLORS[a.status] || "text-muted-foreground"}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{a.action}</div>
                <div className="text-xs text-muted-foreground">
                  {a.action_type && <Badge variant="outline" className="text-[10px] mr-1">{a.action_type}</Badge>}
                  {a.target ? `${a.target}` : ""}
                  {a.organization_id && ` · org: ${a.organization_id.slice(0, 8)}…`}
                </div>
              </div>
              <div className="text-xs text-muted-foreground mono shrink-0">
                {new Date(a.created_at).toLocaleString()}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
