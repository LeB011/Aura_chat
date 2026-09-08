import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
import { Search, StopCircle, Loader2, ChevronRight, WandSparkles, SlidersHorizontal, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const SEARCH_DOMAINS = [
  "Administratif", "Informatique", "Électricien", "Peintre", "Plombier / chauffage",
  "Construction / artisanat", "Immobilier", "Fiduciaire / comptabilité",
  "Marketing / communication", "Restaurant / hôtellerie", "Santé / bien-être",
  "Animaux", "Garage / automobile", "Commerce", "Architecte"
];
const RADII = [5, 10, 20, 30, 50, 100];
const MAX_RESULTS = [5, 10, 20, 25, 50];

function campaignName(form) {
  const target = form.industry?.trim() || "Prospection";
  const area = form.city?.trim() || form.canton?.trim() || "Suisse";
  const stamp = new Intl.DateTimeFormat("fr-CH", { day: "2-digit", month: "2-digit" }).format(new Date());
  return `${target} · ${area} · ${stamp}`;
}

export default function ProspectAI() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useApp();
  const [busy, setBusy] = useState(false);
  const [killing, setKilling] = useState(false);
  const [providers, setProviders] = useState([]);
  const [missionText, setMissionText] = useState("");
  const [missionBusy, setMissionBusy] = useState(false);
  const [missionSummary, setMissionSummary] = useState("");

  const [form, setForm] = useState({
    campaign_name: "",
    industry: "",
    country: "CH",
    canton: "VD",
    city: "Lausanne",
    postal_code: "",
    radius_km: 20,
    max_results: 10,
    sources: ["aura_intelligence"],
    provider: "aura_intelligence",
    filters: {
      has_website: "any",
      has_email: "any",
      has_phone: "any",
      size: "any",
      language: "auto",
      business_domain: "any",
      founded_year_min: "",
      founded_year_max: "",
      exclude_contacted: true,
      exclude_registered: true,
      exclude_no_email: false,
      exclude_duplicates: true,
    },
    ai_analysis_enabled: true,
    service_to_sell: [],
    service_notes: "",
    language: "auto",
    offer: {
      product_name: "",
      description: "",
      main_benefit: "",
      differentiator: "",
      cta_preference: "send_example",
      sender_name: "",
      brand: "",
      website: "",
    },
  });

  useEffect(() => {
    api.get("/prospect-sources")
      .then((r) => setProviders(r.data || []))
      .catch(() => setProviders([]));
  }, []);

  useEffect(() => {
    const prefill = location.state?.prefill;
    if (!prefill) return;
    setForm((current) => ({
      ...current,
      ...prefill,
      filters: { ...current.filters, ...(prefill.filters || {}) },
      offer: { ...current.offer, ...(prefill.offer || {}) },
      service_to_sell: prefill.service_to_sell || current.service_to_sell,
      sources: [prefill.provider || "aura_intelligence"],
      provider: prefill.provider || "aura_intelligence",
    }));
    setMissionText(location.state?.mission || "");
    setMissionSummary(location.state?.mission ? "Critères préparés depuis un prospect existant." : "");
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.state, location.pathname, navigate]);

  const updateFilter = (key, value) => {
    setForm((current) => ({ ...current, filters: { ...current.filters, [key]: value } }));
  };

  const setService = (value) => {
    setForm((current) => ({
      ...current,
      service_to_sell: value.trim() ? [value] : [],
      offer: { ...current.offer, product_name: value },
    }));
  };

  const interpretMission = async () => {
    if (missionText.trim().length < 8) {
      toast.error("Décrivez votre cible en quelques mots.");
      return;
    }
    setMissionBusy(true);
    try {
      const { data } = await api.post("/prospect-ai/mission/parse", { text: missionText, use_ai: true });
      setForm((current) => ({
        ...current,
        ...data,
        campaign_name: current.campaign_name,
        filters: { ...current.filters, ...(data.filters || {}) },
        offer: current.offer,
        service_to_sell: current.service_to_sell,
        service_notes: current.service_notes,
        provider: data.provider || "aura_intelligence",
        sources: [data.provider || "aura_intelligence"],
      }));
      setMissionSummary(data.mission_summary || "Mission comprise. Vérifiez les critères puis lancez la recherche.");
      if (data.needs_industry_confirmation) {
        toast.warning("Aura a besoin que vous confirmiez le domaine recherché.");
      } else {
        toast.success("Mission comprise — recherche préparée");
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Impossible d'interpréter la mission");
    } finally {
      setMissionBusy(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.industry.trim()) {
      toast.error("Indiquez le type d'entreprise recherché.");
      return;
    }
    if (!form.city.trim() && !form.canton.trim()) {
      toast.error("Indiquez une ville ou une zone.");
      return;
    }

    setBusy(true);
    try {
      const payload = {
        ...form,
        campaign_name: form.campaign_name?.trim() || campaignName(form),
        provider: form.provider || "aura_intelligence",
        sources: [form.provider || "aura_intelligence"],
      };
      const { data } = await api.post("/campaigns", payload);
      toast.success(`${data.prospects_count} prospect${data.prospects_count > 1 ? "s" : ""} trouvé${data.prospects_count > 1 ? "s" : ""}`);
      navigate(`/prospects?campaign_id=${data.campaign.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Impossible de lancer la recherche");
    } finally {
      setBusy(false);
    }
  };

  const killSwitch = async () => {
    setKilling(true);
    try {
      await api.post("/security/kill-switch", { active: true });
      toast.warning("Prospect AI stoppé — aucune nouvelle action ne sera déclenchée");
    } finally {
      setKilling(false);
    }
  };

  const selectedService = form.service_to_sell?.[0] || form.offer?.product_name || "";

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">Prospect AI</h1>
          <Badge variant="default" className="text-[10px] uppercase tracking-wider">Disponible</Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Dites simplement qui vous cherchez. Aura s'occupe de la recherche, de la vérification et de la qualification.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <Card className="shadow-sm">
          <CardContent className="p-5 sm:p-6 space-y-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                <Search className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-lg">Trouvez vos prochains clients</h2>
                <p className="text-xs sm:text-sm text-muted-foreground">Trois informations suffisent pour commencer.</p>
              </div>
            </div>

            <div className="grid md:grid-cols-[1.35fr_1fr_150px] gap-4">
              <div className="space-y-1.5">
                <Label>Que recherchez-vous ?</Label>
                <Input
                  data-testid="form-industry"
                  list="search-domains"
                  value={form.industry}
                  onChange={(e) => setForm({ ...form, industry: e.target.value })}
                  placeholder="Ex. fiduciaire, peintre, garage, informatique…"
                  autoComplete="off"
                />
                <datalist id="search-domains">{SEARCH_DOMAINS.map((i) => <option key={i} value={i} />)}</datalist>
              </div>

              <div className="space-y-1.5">
                <Label>Où ?</Label>
                <Input
                  data-testid="form-city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  placeholder="Ex. Lausanne"
                />
              </div>

              <div className="space-y-1.5">
                <Label>Combien ?</Label>
                <Select value={String(form.max_results)} onValueChange={(v) => setForm({ ...form, max_results: parseInt(v, 10) })}>
                  <SelectTrigger data-testid="form-max-results"><SelectValue /></SelectTrigger>
                  <SelectContent>{MAX_RESULTS.map((r) => <SelectItem key={r} value={String(r)}>{r}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Aura Intelligence vérifie et classe les résultats automatiquement.</span>
              </div>
              <Button data-testid="form-submit" type="submit" size="lg" disabled={busy} className="sm:min-w-48">
                {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Recherche…</> : <>Lancer la recherche <ChevronRight className="w-4 h-4 ml-1" /></>}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Accordion type="single" collapsible className="space-y-3">
          <AccordionItem value="mission" className="border rounded-xl px-4 bg-card">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-2 text-left">
                <WandSparkles className="w-4 h-4 text-primary" />
                <div>
                  <div className="font-medium">J'ai une demande plus précise</div>
                  <div className="text-xs text-muted-foreground font-normal">Décrivez votre cible en une phrase et Aura prépare les critères.</div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-4">
              <div className="space-y-3 pt-1">
                <Textarea
                  value={missionText}
                  onChange={(e) => setMissionText(e.target.value)}
                  placeholder="Ex. Trouve 20 fiduciaires à Lausanne, créées depuis 2020, avec un site et un email professionnel."
                  rows={3}
                />
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <Button type="button" variant="secondary" onClick={interpretMission} disabled={missionBusy}>
                    {missionBusy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <WandSparkles className="w-4 h-4 mr-2" />}
                    Comprendre ma demande
                  </Button>
                  {missionSummary && <p className="text-xs text-emerald-700 dark:text-emerald-400">{missionSummary}</p>}
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="advanced" className="border rounded-xl px-4 bg-card">
            <AccordionTrigger className="hover:no-underline py-4">
              <div className="flex items-center gap-2 text-left">
                <SlidersHorizontal className="w-4 h-4" />
                <div>
                  <div className="font-medium">Options avancées</div>
                  <div className="text-xs text-muted-foreground font-normal">Zone précise, filtres, source et personnalisation commerciale.</div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pb-5">
              <div className="space-y-6 pt-1">
                <section className="space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold">Zone de recherche</h3>
                    <p className="text-xs text-muted-foreground">Les valeurs par défaut conviennent à la plupart des recherches locales.</p>
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="space-y-1.5">
                      <Label>Pays</Label>
                      <Select value={form.country} onValueChange={(v) => setForm({ ...form, country: v })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="CH">Suisse</SelectItem><SelectItem value="FR">France</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5"><Label>Canton / région</Label><Input value={form.canton} onChange={(e) => setForm({ ...form, canton: e.target.value })} placeholder="VD" /></div>
                    <div className="space-y-1.5"><Label>Code postal</Label><Input value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} /></div>
                    <div className="space-y-1.5">
                      <Label>Rayon</Label>
                      <Select value={String(form.radius_km)} onValueChange={(v) => setForm({ ...form, radius_km: parseInt(v, 10) })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{RADII.map((r) => <SelectItem key={r} value={String(r)}>{r} km</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                </section>

                <section className="space-y-3 border-t pt-5">
                  <div>
                    <h3 className="text-sm font-semibold">Filtres</h3>
                    <p className="text-xs text-muted-foreground">Laissez “Indifférent” si le critère n'est pas indispensable.</p>
                  </div>
                  <div className="grid sm:grid-cols-3 gap-3">
                    {[['has_website', 'Site web'], ['has_email', 'Email'], ['has_phone', 'Téléphone']].map(([key, label]) => (
                      <div key={key} className="space-y-1.5">
                        <Label>{label}</Label>
                        <Select value={form.filters[key]} onValueChange={(v) => updateFilter(key, v)}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent><SelectItem value="any">Indifférent</SelectItem><SelectItem value="yes">Obligatoire</SelectItem><SelectItem value="no">Sans</SelectItem></SelectContent>
                        </Select>
                      </div>
                    ))}
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="space-y-1.5"><Label>Créée depuis</Label><Input type="number" min="1800" max="2026" placeholder="Ex. 2020" value={form.filters.founded_year_min} onChange={(e) => updateFilter('founded_year_min', e.target.value)} /></div>
                    <div className="space-y-1.5"><Label>Créée jusqu'à</Label><Input type="number" min="1800" max="2026" placeholder="Ex. 2015" value={form.filters.founded_year_max} onChange={(e) => updateFilter('founded_year_max', e.target.value)} /></div>
                    <div className="space-y-1.5">
                      <Label>Taille</Label>
                      <Select value={form.filters.size} onValueChange={(v) => updateFilter('size', v)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{["any", "independent", "1-5", "5-10", "10-50", "50-250", "250+"].map((s) => <SelectItem key={s} value={s}>{s === "any" ? "Toutes" : s === "independent" ? "Indépendant" : s}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Langue</Label>
                      <Select value={form.filters.language} onValueChange={(v) => updateFilter('language', v)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="auto">Automatique</SelectItem><SelectItem value="fr">Français</SelectItem><SelectItem value="de">Allemand</SelectItem><SelectItem value="it">Italien</SelectItem><SelectItem value="en">Anglais</SelectItem><SelectItem value="es">Espagnol</SelectItem></SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {[
                      ["exclude_contacted", "Ignorer les entreprises déjà contactées"],
                      ["exclude_registered", "Ignorer les prospects déjà enregistrés"],
                      ["exclude_no_email", "Ignorer les entreprises sans email"],
                      ["exclude_duplicates", "Supprimer les doublons"],
                    ].map(([key, label]) => (
                      <label key={key} className="flex items-center gap-2 text-sm cursor-pointer py-1">
                        <Checkbox checked={form.filters[key]} onCheckedChange={(v) => updateFilter(key, !!v)} />
                        {label}
                      </label>
                    ))}
                  </div>
                </section>

                <section className="space-y-3 border-t pt-5">
                  <div>
                    <h3 className="text-sm font-semibold">Votre offre <span className="font-normal text-muted-foreground">(optionnel)</span></h3>
                    <p className="text-xs text-muted-foreground">Utile pour préparer ensuite une approche commerciale pertinente. Vous pouvez aussi le compléter plus tard.</p>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5"><Label>Produit / service vendu</Label><Input value={selectedService} onChange={(e) => setService(e.target.value)} placeholder="Ex. gestion administrative externalisée" /></div>
                    <div className="space-y-1.5"><Label>Nom de l'expéditeur</Label><Input value={form.offer.sender_name} onChange={(e) => setForm({ ...form, offer: { ...form.offer, sender_name: e.target.value } })} placeholder="Votre prénom / nom" /></div>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5"><Label>Bénéfice principal</Label><Input value={form.offer.main_benefit} onChange={(e) => setForm({ ...form, offer: { ...form.offer, main_benefit: e.target.value } })} placeholder="Ex. gagner 5 heures par semaine" /></div>
                    <div className="space-y-1.5"><Label>Entreprise / marque</Label><Input value={form.offer.brand} onChange={(e) => setForm({ ...form, offer: { ...form.offer, brand: e.target.value } })} placeholder="Nom de votre entreprise" /></div>
                  </div>
                  <div className="space-y-1.5"><Label>Précision utile</Label><Textarea rows={2} value={form.service_notes} onChange={(e) => setForm({ ...form, service_notes: e.target.value })} placeholder="Une précision qui aidera Aura à comprendre votre offre…" /></div>
                </section>

                <section className="space-y-3 border-t pt-5">
                  <div>
                    <h3 className="text-sm font-semibold">Moteur & analyse</h3>
                    <p className="text-xs text-muted-foreground">Aura Intelligence est recommandé. Ces réglages sont surtout utiles pour les tests et l'administration.</p>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-3 items-end">
                    <div className="space-y-1.5">
                      <Label>Source de recherche</Label>
                      <Select value={form.provider} onValueChange={(v) => setForm({ ...form, provider: v, sources: [v] })}>
                        <SelectTrigger data-testid="form-provider"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {providers.filter((p) => ["mock", "aura_intelligence", "tinyfish", "google_places"].includes(p.key)).map((p) => (
                            <SelectItem key={p.key} value={p.key} disabled={p.requires_credentials && !p.is_configured}>
                              {p.label}{p.requires_credentials && !p.is_configured ? " — Non configuré" : ""}
                            </SelectItem>
                          ))}
                          {!providers.length && <SelectItem value="aura_intelligence">Aura Intelligence</SelectItem>}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div><div className="text-sm font-medium">Analyse IA</div><div className="text-xs text-muted-foreground">Score et opportunités</div></div>
                      <Switch data-testid="form-ai-analysis" checked={form.ai_analysis_enabled} onCheckedChange={(v) => setForm({ ...form, ai_analysis_enabled: v })} />
                    </div>
                  </div>
                </section>

                <section className="border-t pt-5">
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                        <StopCircle className="w-4 h-4 mr-2" />Arrêter Prospect AI
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t("prospect.stop_agent")}</AlertDialogTitle>
                        <AlertDialogDescription>{t("prospect.kill_confirm")}</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
                        <AlertDialogAction onClick={killSwitch} disabled={killing}>Arrêter</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </section>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </form>
    </div>
  );
}
