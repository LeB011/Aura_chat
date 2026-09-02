import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";
import { toast } from "sonner";

const ROLES = ["member", "admin", "owner", "superadmin"];

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const load = async () => setUsers((await api.get("/admin/users", { params: q ? { q } : {} })).data);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q]);

  const changeRole = async (id, role) => {
    await api.patch(`/admin/users/${id}`, { role });
    toast.success("Rôle mis à jour");
    load();
  };
  const toggleSuspend = async (u) => {
    await api.patch(`/admin/users/${u.id}`, { suspended: !u.suspended });
    toast.success(u.suspended ? "Compte réactivé" : "Compte suspendu");
    load();
  };

  return (
    <div className="space-y-4">
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input data-testid="admin-users-search" placeholder="Rechercher email ou nom..." value={q}
          onChange={(e) => setQ(e.target.value)} className="pl-9" />
      </div>
      <Card>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {users.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">Aucun utilisateur.</div>}
            {users.map((u) => (
              <div key={u.id} data-testid={`admin-user-${u.id}`} className="p-4 flex flex-col md:flex-row md:items-center gap-3 md:gap-4">
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{u.full_name}</div>
                  <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                  <div className="text-[11px] text-muted-foreground mono">org: {u.organization_id?.slice(0, 8)}…</div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Select value={u.role} onValueChange={(v) => changeRole(u.id, v)}>
                    <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                  </Select>
                  {u.suspended && <Badge variant="destructive" className="text-[10px]">Suspendu</Badge>}
                  <Button size="sm" variant={u.suspended ? "outline" : "destructive"} onClick={() => toggleSuspend(u)}>
                    {u.suspended ? "Réactiver" : "Suspendre"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
