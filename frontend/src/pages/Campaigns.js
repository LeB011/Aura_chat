import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExternalLink, Trash2 } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS = {
  draft: "secondary", active: "default", paused: "outline", done: "secondary", archived: "outline",
};

export default function Campaigns() {
  const [items, setItems] = useState([]);

  const load = async () => {
    const { data } = await api.get("/campaigns");
    setItems(data);
  };
  useEffect(() => { load(); }, []);

  const setStatus = async (id, status) => {
    await api.patch(`/campaigns/${id}`, { status });
    toast.success("Campagne mise à jour");
    load();
  };
  const del = async (id) => {
    if (!confirm("Supprimer cette campagne et ses prospects ?")) return;
    await api.delete(`/campaigns/${id}`);
    toast.success("Supprimée");
    load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Campagnes</h1>
        <p className="text-sm text-muted-foreground mt-1">Gérez toutes vos campagnes de prospection.</p>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground text-xs uppercase border-b border-border">
                  <th className="px-4 py-3">Nom</th>
                  <th className="px-4 py-3">Cible</th>
                  <th className="px-4 py-3">Prospects</th>
                  <th className="px-4 py-3">Qualifiés</th>
                  <th className="px-4 py-3">Messages</th>
                  <th className="px-4 py-3">RDV</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && <tr><td colSpan={8} className="p-10 text-center text-muted-foreground">Aucune campagne pour l'instant.</td></tr>}
                {items.map((c) => (
                  <tr key={c.id} data-testid={`campaign-row-${c.id}`} className="border-b border-border hover:bg-accent/40">
                    <td className="px-4 py-3 font-medium">{c.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.criteria?.industry} — {c.criteria?.city}</td>
                    <td className="px-4 py-3 mono">{c.stats?.prospects_found || 0}</td>
                    <td className="px-4 py-3 mono">{c.stats?.qualified || 0}</td>
                    <td className="px-4 py-3 mono">{(c.stats?.messages_prepared || 0) + "/" + (c.stats?.messages_sent || 0)}</td>
                    <td className="px-4 py-3 mono">{c.stats?.meetings || 0}</td>
                    <td className="px-4 py-3">
                      <Select value={c.status} onValueChange={(v) => setStatus(c.id, v)}>
                        <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {["draft","active","paused","done","archived"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/prospects?campaign_id=${c.id}`}>
                        <Button size="sm" variant="ghost" className="h-8">Voir <ExternalLink className="w-3.5 h-3.5 ml-1" /></Button>
                      </Link>
                      <Button size="sm" variant="ghost" className="h-8 text-destructive" onClick={() => del(c.id)}><Trash2 className="w-3.5 h-3.5" /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
