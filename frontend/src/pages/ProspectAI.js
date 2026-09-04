import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Search, StopCircle, Plus, Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const SEARCH_DOMAINS = [
  "Administratif", "Informatique", "Électricien", "Peintre", "Plombier / chauffage",
  "Construction / artisanat", "Immobilier", "Fiduciaire / comptabilité",
  "Marketing / communication", "Restaurant / hôtellerie", "Santé / bien-être",
  "Animaux", "Garage / automobile", "Commerce", "Architecte"
];
const RADII = [5, 10, 20, 30, 50, 100];
const MAX_RESULTS = [5, 10, 20, 25, 50];
const BUSINESS_DOMAINS = [
  ["any", "Tous les domaines"], ["administratif", "Administratif"], ["informatique", "Informatique"],
  ["électricité", "Électricité"], ["plomberie/chauffage", "Plomberie / chauffage"],
  ["marketing/communication", "Marketing / communication"], ["comptabilité/fiduciaire", "Comptabilité / fiduciaire"],
  ["immobilier", "Immobilier"], ["construction/artisanat", "Construction / artisanat"],
  ["restauration/hôtellerie", "Restauration / hôtellerie"], ["santé/bien-être", "Santé / bien-être"], ["animaux", "Animaux"],
];
const SERVICES = [
  "Agent de prospection IA", "Assistant administratif IA", "Automatisation des emails",
  "Réponses automatiques clients", "Relance automatique des devis", "Création de devis",
  "Qualification de leads", "Gestion CRM", "Prise de rendez-vous", "Création de contenu",
  "Assistant interne entreprise", "Automatisation personnalisée",
];

export default function ProspectAI() {
  const navigate = useNavigate();
  const { t } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [killing, setKilling] = useState(false);
  const [form, setForm] = useState({
    campaign_name: "Nouvelle campagne",
    industry: "",
    country: "CH", canton: "VD", city: "Lausanne", postal_code: "",
    radius_km: 20, max_results: 10,
    sources: [], provider: "mock",
    filters: { has_website: "any", has_email: "any", has_phone: "any", size: "any", language: "auto",
                business_domain: "any", founded_year_min: "", founded_year_max: "",
                exclude_contacted: true, exclude_registered: true, exclude_no_email: false, exclude_duplicates: true },
    ai_analysis_enabled: true,
    service_to_sell: ["Agent de prospection IA"],
    service_notes: "",
    language: "auto",
    offer: {
      product_name: "Aura Hub / Prospect AI",
      description: "Outil de prospection B2B assisté par IA qui trouve, qualifie et prépare des prises de contact personnalisées.",
      main_benefit: "Réduire le temps nécessaire pour identifier et qualifier de nouvelles opportunités commerciales.",
      differentiator: "Aura réunit recherche, qualification et préparation des messages dans un même flux.",
      cta_preference: "send_example", sender_name: "Bryan", brand: "Aura Hub", website: "",
    },
  });
  const [providers, setProviders] = useState([]);
  useEffect(() => { api.get("/prospect-sources").then((r) => setProviders(r.data || [])).catch(() => setProviders([])); }, []);
  const toggleService = (s) => {
    const has = form.service_to_sell.includes(s);
    setForm({ ...form, service_to_sell: has ? form.service_to_sell.filter((x) => x !== s) : [...form.service_to_sell, s] });
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/campaigns", form);
      toast.success(`Campagne créée — ${data.prospects_count} prospects trouvés`);
      navigate(`/prospects?campaign_id=${data.campaign.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    } finally { setBusy(false); }
  };

  const killSwitch = async () => {
    setKilling(true);
    try {
      await api.post("/security/kill-switch", { active: true });
      toast.warning("Prospect AI stoppé — aucune nouvelle action ne sera déclenchée");
    } finally { setKilling(false); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-semibold tracking-tight">Prospect AI</h1>
            <Badge variant="default" className="text-[10px] uppercase tracking-wider">Actif</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Trouvez, analysez et qualifiez automatiquement vos prochains clients.
          </p>
        </div>
        <div className="flex gap-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button data-testid="prospect-killswitch" variant="destructive" size="sm">
                <StopCircle className="w-4 h-4 mr-1.5" />{t("prospect.stop_agent")}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("prospect.stop_agent")}</AlertDialogTitle>
                <AlertDialogDescription>{t("prospect.kill_confirm")}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
                <AlertDialogAction data-testid="prospect-killswitch-confirm" onClick={killSwitch} disabled={killing}>
                  Arrêter
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button data-testid="prospect-new-search" onClick={() => setShowForm((v) => !v)}>
            <Plus className="w-4 h-4 mr-1.5" />{t("prospect.new_search")}
          </Button>
        </div>
      </div>

      {!showForm && (
        <Card className="border-dashed">
          <CardContent className="p-10 text-center space-y-3">
            <div className="w-12 h-12 rounded-lg bg-secondary mx-auto flex items-center justify-center">
              <Search className="w-6 h-6 text-muted-foreground" />
            </div>
            <h3 className="font-medium">Lancez votre première recherche</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Décrivez votre cible et Prospect AI trouvera, analysera et qualifiera les entreprises correspondantes.
            </p>
            <Button data-testid="prospect-cta" onClick={() => setShowForm(true)}>
              <Plus className="w-4 h-4 mr-1.5" />{t("prospect.new_search")}
            </Button>
          </CardContent>
        </Card>
      )}

      {showForm && (
        <form onSubmit={submit} className="space-y-4">
          <Card>
            <CardContent className="p-6 space-y-4">
              <h3 className="font-semibold">Cible</h3>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Nom de la campagne</Label>
                  <Input data-testid="form-campaign-name" value={form.campaign_name} onChange={(e) => setForm({...form, campaign_name: e.target.value})} required />
                </div>
                <div className="space-y-1.5">
                  <Label>Domaine recherché</Label>
                  <Input
                    data-testid="form-industry"
                    list="search-domains"
                    value={form.industry}
                    onChange={(e) => setForm({...form, industry: e.target.value})}
                    placeholder="ex. administratif, peintre, informatique, vétérinaire..."
                    required
                  />
                  <datalist id="search-domains">{SEARCH_DOMAINS.map((i) => <option key={i} value={i} />)}</datalist>
                  <p className="text-xs text-muted-foreground">
                    C'est la cible principale de la recherche. Aura interprète aussi les termes libres : vous n'avez plus besoin de choisir un type d'entreprise séparément.
                  </p>
                </div>
              </div>
              <div className="grid md:grid-cols-4 gap-4">
                <div className="space-y-1.5"><Label>Pays</Label>
                  <Select value={form.country} onValueChange={(v) => setForm({...form, country: v})}>
                    <SelectTrigger data-testid="form-country"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="CH">Suisse</SelectItem><SelectItem value="FR">France</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5"><Label>Canton</Label>
                  <Input value={form.canton} onChange={(e) => setForm({...form, canton: e.target.value})} placeholder="VD" />
                </div>
                <div className="space-y-1.5"><Label>Ville</Label>
                  <Input data-testid="form-city" value={form.city} onChange={(e) => setForm({...form, city: e.target.value})} />
                </div>
                <div className="space-y-1.5"><Label>Code postal</Label>
                  <Input value={form.postal_code} onChange={(e) => setForm({...form, postal_code: e.target.value})} />
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1.5"><Label>Rayon</Label>
                  <Select value={String(form.radius_km)} onValueChange={(v) => setForm({...form, radius_km: parseInt(v)})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{RADII.map((r) => <SelectItem key={r} value={String(r)}>{r} km</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5"><Label>Nombre maximum de prospects</Label>
                  <Select value={String(form.max_results)} onValueChange={(v) => setForm({...form, max_results: parseInt(v)})}>
                    <SelectTrigger data-testid="form-max-results"><SelectValue /></SelectTrigger>
                    <SelectContent>{MAX_RESULTS.map((r) => <SelectItem key={r} value={String(r)}>{r}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <h3 className="font-semibold">Source de recherche</h3>
              <p className="text-xs text-muted-foreground">Choisissez le provider réellement utilisé. Aucun faux annuaire n'est affiché.</p>
              <Select value={form.provider} onValueChange={(v) => setForm({...form, provider: v, sources: [v]})}>
                <SelectTrigger data-testid="form-provider"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {providers.filter((p) => ["mock", "aura_intelligence", "tinyfish", "google_places"].includes(p.key)).map((p) => (
                    <SelectItem key={p.key} value={p.key} disabled={p.requires_credentials && !p.is_configured}>
                      {p.label}{p.requires_credentials && !p.is_configured ? " — Non configuré" : ""}
                    </SelectItem>
                  ))}
                  {!providers.length && <SelectItem value="mock">Mock (démo)</SelectItem>}
                </SelectContent>
              </Select>
              {form.provider === "mock" && <div className="text-xs text-amber-700">Données simulées — aucune entreprise réelle ne sera recherchée.</div>}
              {form.provider === "aura_intelligence" && <div className="text-xs text-emerald-700"><strong>Recommandé :</strong> Aura fusionne automatiquement Google Places si configuré et TinyFish. Sans clé Google, elle continue avec TinyFish uniquement.</div>}
              {form.provider === "tinyfish" && <div className="text-xs text-emerald-700">Recherche réelle TinyFish Search + Fetch sur le web public. Le Mode Test bloque toujours tout envoi externe.</div>}
              {form.provider === "google_places" && <div className="text-xs text-emerald-700">Recherche réelle Google Places. Le Mode Test bloque toujours tout envoi externe.</div>}
            </CardContent>
          </Card>

          <Accordion type="single" collapsible>
            <AccordionItem value="filters">
              <Card>
                <AccordionTrigger className="px-6 py-4 hover:no-underline">
                  <span className="font-semibold">Filtres avancés</span>
                </AccordionTrigger>
                <AccordionContent>
                  <CardContent className="pt-0 space-y-4">
                    <div className="grid md:grid-cols-3 gap-4">
                      {["has_website", "has_email", "has_phone"].map((k) => (
                        <div key={k} className="space-y-1.5">
                          <Label className="capitalize">{k.replace(/_/g, " ")}</Label>
                          <Select value={form.filters[k]} onValueChange={(v) => setForm({...form, filters: {...form.filters, [k]: v}})}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="yes">Oui</SelectItem><SelectItem value="no">Non</SelectItem><SelectItem value="any">Indifférent</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      ))}
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-1.5"><Label>Créée depuis l'année</Label>
                        <Input type="number" min="1800" max="2026" placeholder="ex. 2020" value={form.filters.founded_year_min} onChange={(e) => setForm({...form, filters:{...form.filters, founded_year_min:e.target.value}})} />
                      </div>
                      <div className="space-y-1.5"><Label>Créée avant / jusqu'à</Label>
                        <Input type="number" min="1800" max="2026" placeholder="ex. 2010" value={form.filters.founded_year_max} onChange={(e) => setForm({...form, filters:{...form.filters, founded_year_max:e.target.value}})} />
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">L'année de création n'est filtrée que lorsqu'elle est explicitement trouvée sur une source publique. Les entreprises dont l'année est inconnue sont exclues si vous activez ce filtre.</p>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-1.5"><Label>Taille entreprise</Label>
                        <Select value={form.filters.size} onValueChange={(v) => setForm({...form, filters: {...form.filters, size: v}})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {["any","independent","1-5","5-10","10-50","50-250","250+"].map((s) => <SelectItem key={s} value={s}>{s === "any" ? "Toutes" : s}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1.5"><Label>Langue</Label>
                        <Select value={form.filters.language} onValueChange={(v) => setForm({...form, filters: {...form.filters, language: v}})}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="auto">Automatique</SelectItem><SelectItem value="fr">Français</SelectItem><SelectItem value="de">Allemand</SelectItem>
                            <SelectItem value="it">Italien</SelectItem><SelectItem value="en">Anglais</SelectItem><SelectItem value="es">Espagnol</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="space-y-2 pt-2">
                      <div className="text-sm font-medium">Exclure :</div>
                      {[
                        ["exclude_contacted", "Entreprises déjà contactées"],
                        ["exclude_registered", "Prospects déjà enregistrés"],
                        ["exclude_no_email", "Entreprises sans email"],
                        ["exclude_duplicates", "Doublons"],
                      ].map(([k, l]) => (
                        <label key={k} className="flex items-center gap-2 text-sm cursor-pointer">
                          <Checkbox checked={form.filters[k]} onCheckedChange={(v) => setForm({...form, filters: {...form.filters, [k]: !!v}})} />
                          {l}
                        </label>
                      ))}
                    </div>
                  </CardContent>
                </AccordionContent>
              </Card>
            </AccordionItem>
          </Accordion>

          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">Analyse IA</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Analyser automatiquement chaque entreprise avec l'IA (score, opportunités, arguments).</p>
                </div>
                <Switch data-testid="form-ai-analysis" checked={form.ai_analysis_enabled} onCheckedChange={(v) => setForm({...form, ai_analysis_enabled: v})} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <h3 className="font-semibold">Que souhaitez-vous vendre ?</h3>
              <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-2">
                {SERVICES.map((s) => (
                  <label key={s} className="flex items-center gap-2 p-2 rounded-md hover:bg-accent/50 cursor-pointer text-sm">
                    <Checkbox checked={form.service_to_sell.includes(s)} onCheckedChange={() => toggleService(s)} />
                    {s}
                  </label>
                ))}
              </div>
              <div className="space-y-1.5">
                <Label>Autre / précisions</Label>
                <Textarea rows={2} value={form.service_notes} onChange={(e) => setForm({...form, service_notes: e.target.value})} />
              </div>
              <div className="border-t pt-4 space-y-3">
                <div className="font-medium text-sm">Offre commerciale pour personnaliser les messages</div>
                <div className="grid md:grid-cols-2 gap-3">
                  <div><Label>Produit / service</Label><Input value={form.offer.product_name} onChange={(e) => setForm({...form, offer:{...form.offer, product_name:e.target.value}})} /></div>
                  <div><Label>Nom de l'expéditeur</Label><Input value={form.offer.sender_name} onChange={(e) => setForm({...form, offer:{...form.offer, sender_name:e.target.value}})} /></div>
                </div>
                <div><Label>Description de l'offre</Label><Textarea rows={2} value={form.offer.description} onChange={(e) => setForm({...form, offer:{...form.offer, description:e.target.value}})} /></div>
                <div><Label>Bénéfice principal</Label><Input value={form.offer.main_benefit} onChange={(e) => setForm({...form, offer:{...form.offer, main_benefit:e.target.value}})} /></div>
                <div><Label>Différenciateur</Label><Input value={form.offer.differentiator} onChange={(e) => setForm({...form, offer:{...form.offer, differentiator:e.target.value}})} /></div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-2 sticky bottom-0 bg-background py-3 border-t">
            <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Annuler</Button>
            <Button data-testid="form-submit" type="submit" disabled={busy}>
              {busy ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Recherche en cours…</> :
                <>Lancer la recherche <ChevronRight className="w-4 h-4 ml-1" /></>}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
