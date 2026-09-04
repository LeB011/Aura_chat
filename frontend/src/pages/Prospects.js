import React, { useEffect, useState, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2, ExternalLink, Download, Filter, Search as SearchIcon } from "lucide-react";
import { toast } from "sonner";

const STATUS_LABELS = {
  new: "Nouveau", to_analyze: "À analyser", analyzed: "Analysé", to_contact: "À contacter",
  message_ready: "Message prêt", validated: "Validé", contacted: "Contacté", replied: "Répondu",
  interested: "Intéressé", meeting: "Rendez-vous", customer: "Client", refused: "Refus",
  do_not_contact: "Ne plus contacter",
};

function scoreColor(s) {
  if (s >= 81) return "bg-emerald-500";
  if (s >= 61) return "bg-emerald-400";
  if (s >= 31) return "bg-amber-400";
  return "bg-slate-300 dark:bg-slate-600";
}

export default function Prospects() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [minScore, setMinScore] = useState("0");
  const [businessDomain, setBusinessDomain] = useState("all");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [params] = useSearchParams();
  const campaignId = params.get("campaign_id");

  const load = async () => {
    const query = {};
    if (campaignId) query.campaign_id = campaignId;
    if (status !== "all") query.status = status;
    if (q) query.q = q;
    if (parseInt(minScore) > 0) query.min_score = parseInt(minScore);
    if (businessDomain !== "all") query.business_domain = businessDomain;
    if (yearMin) query.founded_year_min = parseInt(yearMin);
    if (yearMax) query.founded_year_max = parseInt(yearMax);
    const { data } = await api.get("/prospects", { params: query });
    setItems(data);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [status, minScore, businessDomain, yearMin, yearMax, campaignId]);

  const toggleAll = (v) => setSelected(v ? new Set(items.map((i) => i.id)) : new Set());
  const toggleOne = (id) => {
    const n = new Set(selected);
    n.has(id) ? n.delete(id) : n.add(id);
    setSelected(n);
  };

  const bulkDelete = async () => {
    if (!selected.size) return;
    await api.post("/prospects/bulk", { action: "delete", ids: [...selected] });
    toast.success(`${selected.size} prospect(s) supprimé(s)`);
    setSelected(new Set()); load();
  };
  const bulkStatus = async (newStatus) => {
    if (!selected.size) return;
    await api.post("/prospects/bulk", { action: "set_status", ids: [...selected], status: newStatus });
    toast.success("Statut mis à jour");
    setSelected(new Set()); load();
  };

  const exportCsv = () => {
    const headers = ["company_name","business_domain","founded_year","industry","city","website","email","phone","status","score","source"];
    const rows = items.map((p) => headers.map((h) => {
      if (h === "score") return p.ai_analysis?.ai_opportunity_score || "";
      return (p[h] || "").toString().replace(/"/g, '""');
    }).map((v) => `"${v}"`).join(","));
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "prospects.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = useMemo(() => {
    if (!q) return items;
    const ql = q.toLowerCase();
    return items.filter((i) => (i.company_name || "").toLowerCase().includes(ql) || (i.city || "").toLowerCase().includes(ql));
  }, [items, q]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Prospects</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {campaignId ? "Prospects de la campagne sélectionnée" : "Tous vos prospects en un coup d'œil"}
        </p>
      </div>

      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-col md:flex-row gap-2">
            <div className="relative flex-1">
              <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input data-testid="prospects-search" placeholder="Rechercher entreprise, ville..." value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
            </div>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger data-testid="prospects-status-filter" className="md:w-56"><SelectValue placeholder="Statut" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les statuts</SelectItem>
                {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={minScore} onValueChange={setMinScore}>
              <SelectTrigger className="md:w-44"><SelectValue placeholder="Score min." /></SelectTrigger>
              <SelectContent>
                {[0,31,61,81].map((s) => <SelectItem key={s} value={String(s)}>{s === 0 ? "Tous scores" : `≥ ${s}`}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={businessDomain} onValueChange={setBusinessDomain}>
              <SelectTrigger className="md:w-56"><SelectValue placeholder="Domaine" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous domaines</SelectItem>
                {["administratif","informatique","électricité","plomberie/chauffage","marketing/communication","comptabilité/fiduciaire","immobilier","construction/artisanat","restauration/hôtellerie","santé/bien-être","animaux"].map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input className="md:w-32" type="number" placeholder="Créée ≥" value={yearMin} onChange={(e)=>setYearMin(e.target.value)} />
            <Input className="md:w-32" type="number" placeholder="Créée ≤" value={yearMax} onChange={(e)=>setYearMax(e.target.value)} />
            <Button data-testid="prospects-export" variant="outline" onClick={exportCsv}><Download className="w-4 h-4 mr-1.5" />CSV</Button>
          </div>

          {selected.size > 0 && (
            <div className="flex items-center gap-2 py-2 px-3 rounded-md bg-accent">
              <span className="text-sm">{selected.size} sélectionné(s)</span>
              <Select onValueChange={bulkStatus}>
                <SelectTrigger className="h-8 w-44"><SelectValue placeholder="Changer statut" /></SelectTrigger>
                <SelectContent>
                  {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="sm" variant="destructive" onClick={bulkDelete}><Trash2 className="w-4 h-4 mr-1.5" />Supprimer</Button>
            </div>
          )}

          <div className="overflow-x-auto -mx-4 hidden md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider border-b border-border">
                  <th className="px-4 py-2"><Checkbox checked={selected.size === filtered.length && filtered.length > 0} onCheckedChange={toggleAll} /></th>
                  <th className="px-4 py-2">Score</th>
                  <th className="px-4 py-2">Vérif.</th>
                  <th className="px-4 py-2">Entreprise</th>
                  <th className="px-4 py-2">Domaine</th>
                  <th className="px-4 py-2">Création</th>
                  <th className="px-4 py-2">Métier</th>
                  <th className="px-4 py-2">Ville</th>
                  <th className="px-4 py-2">Email</th>
                  <th className="px-4 py-2">Statut</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan={11} className="p-10 text-center text-muted-foreground">
                    Aucun prospect. Lancez une recherche depuis Prospect AI ou ajoutez des données démo.
                  </td></tr>
                )}
                {filtered.map((p) => {
                  const score = p.qualification_score ?? p.ai_analysis?.ai_opportunity_score ?? 0;
                  return (
                    <tr key={p.id} data-testid={`prospect-row-${p.id}`} className="border-b border-border hover:bg-accent/40">
                      <td className="px-4 py-3"><Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleOne(p.id)} /></td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className={`w-1.5 h-6 rounded-sm ${scoreColor(score)}`} />
                          <span className="mono text-xs">{score}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="text-[10px]">{p.verification_score || 0}%</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Link to={`/prospects/${p.id}`} className="font-medium hover:underline">{p.company_name}</Link>
                        {p.is_demo && <Badge variant="secondary" className="ml-2 text-[10px]">DEMO</Badge>}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{p.business_domain || "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{p.founded_year || "Inconnue"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{p.industry}</td>
                      <td className="px-4 py-3 text-muted-foreground">{p.city}</td>
                      <td className="px-4 py-3 text-muted-foreground truncate max-w-[180px]">{p.email || "—"}</td>
                      <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{STATUS_LABELS[p.status] || p.status}</Badge></td>
                      <td className="px-4 py-3 text-right">
                        <Link to={`/prospects/${p.id}`}>
                          <Button data-testid={`prospect-open-${p.id}`} size="sm" variant="ghost" className="h-8">Ouvrir <ExternalLink className="w-3.5 h-3.5 ml-1" /></Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {filtered.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground border border-dashed border-border rounded-md">
                Aucun prospect.
              </div>
            )}
            {filtered.map((p) => {
              const score = p.qualification_score ?? p.ai_analysis?.ai_opportunity_score ?? 0;
              return (
                <div key={p.id} data-testid={`prospect-mobile-${p.id}`} className="border border-border rounded-md p-3 bg-card">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2 min-w-0 flex-1">
                      <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleOne(p.id)} className="mt-1" />
                      <div className="min-w-0 flex-1">
                        <Link to={`/prospects/${p.id}`} className="font-medium block truncate">{p.company_name}</Link>
                        <div className="text-xs text-muted-foreground truncate">{p.business_domain || p.industry} · {p.city}</div>
                        <div className="text-xs text-muted-foreground">Création : {p.founded_year || "inconnue"}</div>
                        <div className="text-xs text-muted-foreground">Vérification : {p.verification_score || 0}% · {(p.evidence_sources || []).join(" + ") || "source unique"}</div>
                        {p.email && <div className="text-xs text-muted-foreground truncate">{p.email}</div>}
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-[10px]">{STATUS_LABELS[p.status] || p.status}</Badge>
                          {p.is_demo && <Badge variant="secondary" className="text-[10px]">DEMO</Badge>}
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`w-1.5 h-8 rounded-sm ${scoreColor(score)} ml-auto`} />
                      <div className="mono text-sm font-semibold mt-1">{score}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
