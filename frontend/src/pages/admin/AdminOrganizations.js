import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { toast } from "sonner";

const PLANS = ["demo", "starter", "business", "premium"];

export default function AdminOrganizations() {
  const [orgs, setOrgs] = useState([]);
  const load = async () => setOrgs((await api.get("/admin/organizations")).data);
  useEffect(() => { load(); }, []);

  const suspend = async (id) => {
    await api.post(`/admin/organizations/${id}/suspend`);
    toast.warning("Organisation suspendue");
    load();
  };
  const reactivate = async (id) => {
    await api.post(`/admin/organizations/${id}/reactivate`);
    toast.success("Organisation réactivée");
    load();
  };
  const changePlan = async (id, plan) => {
    await api.patch(`/admin/organizations/${id}`, { plan });
    toast.success("Plan mis à jour");
    load();
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-muted-foreground border-b border-border">
                <th className="px-4 py-3">Organisation</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Utilisateurs</th>
                <th className="px-4 py-3">Prospects</th>
                <th className="px-4 py-3">Campagnes</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {orgs.length === 0 && <tr><td colSpan={8} className="p-8 text-center text-muted-foreground">Aucune organisation.</td></tr>}
              {orgs.map((o) => (
                <tr key={o.id} data-testid={`admin-org-${o.id}`} className="border-b border-border">
                  <td className="px-4 py-3 font-medium">
                    {o.name}
                    <div className="text-[10px] text-muted-foreground mono">{o.id}</div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{o.owner?.email || "—"}</td>
                  <td className="px-4 py-3">
                    <Select value={o.plan} onValueChange={(v) => changePlan(o.id, v)}>
                      <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
                      <SelectContent>{PLANS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                    </Select>
                  </td>
                  <td className="px-4 py-3 mono">{o.users_count}</td>
                  <td className="px-4 py-3 mono">{o.prospects_count}</td>
                  <td className="px-4 py-3 mono">{o.campaigns_count}</td>
                  <td className="px-4 py-3">
                    {o.suspended ? <Badge variant="destructive" className="text-[10px]">Suspendue</Badge>
                                  : <Badge className="text-[10px]">Active</Badge>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {o.suspended ? (
                      <Button size="sm" variant="outline" onClick={() => reactivate(o.id)}>Réactiver</Button>
                    ) : (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="destructive">Suspendre</Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Suspendre {o.name} ?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Les utilisateurs de cette organisation ne pourront plus se connecter.
                              Les données sont préservées et l'organisation pourra être réactivée à tout moment.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Annuler</AlertDialogCancel>
                            <AlertDialogAction data-testid={`suspend-confirm-${o.id}`} onClick={() => suspend(o.id)}>
                              Suspendre
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Mobile */}
        <div className="md:hidden divide-y divide-border">
          {orgs.map((o) => (
            <div key={o.id} className="p-4 space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">{o.name}</div>
                  <div className="text-xs text-muted-foreground">{o.owner?.email || "—"}</div>
                </div>
                {o.suspended ? <Badge variant="destructive" className="text-[10px]">Suspendue</Badge>
                              : <Badge className="text-[10px]">Active</Badge>}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                <div>Users: <span className="mono text-foreground">{o.users_count}</span></div>
                <div>Prospects: <span className="mono text-foreground">{o.prospects_count}</span></div>
                <div>Camp.: <span className="mono text-foreground">{o.campaigns_count}</span></div>
              </div>
              <div className="flex gap-2">
                <Select value={o.plan} onValueChange={(v) => changePlan(o.id, v)}>
                  <SelectTrigger className="h-8 flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>{PLANS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
                {o.suspended
                  ? <Button size="sm" variant="outline" onClick={() => reactivate(o.id)}>Réactiver</Button>
                  : <Button size="sm" variant="destructive" onClick={() => suspend(o.id)}>Suspendre</Button>}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
