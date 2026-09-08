import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

const PLANS=["demo","starter","business","premium"];
export default function AdminOrganizations(){
 const [orgs,setOrgs]=useState([]); const [open,setOpen]=useState(null); const [agents,setAgents]=useState({});
 const load=async()=>setOrgs((await api.get("/admin/organizations")).data); useEffect(()=>{load();},[]);
 const changePlan=async(id,plan)=>{await api.patch(`/admin/organizations/${id}`,{plan});toast.success("Plan mis à jour");load();};
 const toggleOrg=async(o)=>{ if(open===o.id){setOpen(null);return;} setOpen(o.id); try{setAgents({...agents,[o.id]:(await api.get(`/admin/organizations/${o.id}/agents`)).data});}catch(e){toast.error("Impossible de charger les agents");}};
 const setAgent=async(orgId,a,enabled)=>{ await api.patch(`/admin/organizations/${orgId}/agents/${a.key}`,{enabled}); setAgents({...agents,[orgId]:(agents[orgId]||[]).map(x=>x.key===a.key?{...x,enabled}:x)}); toast.success(`${a.name} ${enabled?'activé':'désactivé'}`); };
 const suspend=async(id)=>{await api.post(`/admin/organizations/${id}/suspend`);toast.warning("Organisation suspendue");load();};
 const reactivate=async(id)=>{await api.post(`/admin/organizations/${id}/reactivate`);toast.success("Organisation réactivée");load();};
 return <Card><CardContent className="p-4 space-y-3"><div><h3 className="font-semibold">Organisations & accès aux agents</h3><p className="text-xs text-muted-foreground">Super Admin : choisissez précisément quels agents chaque client peut utiliser. Les agents à venir peuvent rester visibles mais désactivés.</p></div>
 {orgs.map(o=><div key={o.id} className="border rounded-md p-3 space-y-3">
   <div className="flex flex-col md:flex-row md:items-center gap-3"><div className="flex-1"><div className="font-medium">{o.name}</div><div className="text-xs text-muted-foreground">{o.owner?.email||"—"} · {o.prospects_count||0} prospects</div></div>
   <Select value={o.plan} onValueChange={v=>changePlan(o.id,v)}><SelectTrigger className="w-32"><SelectValue/></SelectTrigger><SelectContent>{PLANS.map(p=><SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select>
   {o.suspended?<Button size="sm" variant="outline" onClick={()=>reactivate(o.id)}>Réactiver</Button>:<Button size="sm" variant="destructive" onClick={()=>suspend(o.id)}>Suspendre</Button>}
   <Button size="sm" variant="outline" onClick={()=>toggleOrg(o)}>{open===o.id?"Fermer":"Gérer les agents"}</Button></div>
   {open===o.id&&<div className="grid md:grid-cols-2 gap-2 pt-2 border-t">{(agents[o.id]||[]).map(a=><div key={a.key} className="flex items-center justify-between gap-2 rounded border p-2"><div><div className="text-sm font-medium">{a.name}</div><div className="text-[10px] text-muted-foreground">{a.status} · min. {a.minimum_plan}</div></div><Switch checked={!!a.enabled} onCheckedChange={v=>setAgent(o.id,a,v)}/></div>)}</div>}
 </div>)}</CardContent></Card>;
}
