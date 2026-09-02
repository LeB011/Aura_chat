import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowLeft, Sparkles, Send, Copy, Mail, Phone, Globe, MapPin, Loader2, CheckCircle } from "lucide-react";
import { toast } from "sonner";

const STATUS_LABELS = {
  new: "Nouveau", to_analyze: "À analyser", analyzed: "Analysé", to_contact: "À contacter",
  message_ready: "Message prêt", validated: "Validé", contacted: "Contacté", replied: "Répondu",
  interested: "Intéressé", meeting: "Rendez-vous", customer: "Client", refused: "Refus",
  do_not_contact: "Ne plus contacter",
};

export default function ProspectDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [messages, setMessages] = useState([]);
  const [genOpts, setGenOpts] = useState({
    channel: "email", tone: "professionnel", length: "normal", language: "fr", objective: "presentation", strategy: "professional",
  });
  const [gen, setGen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [note, setNote] = useState("");

  const load = async () => {
    const [pd, ms] = await Promise.all([
      api.get(`/prospects/${id}`),
      api.get(`/messages`, { params: { prospect_id: id } }),
    ]);
    setP(pd.data);
    setMessages(ms.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!p) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  const a = p.ai_analysis || {};
  const score = p.qualification_score ?? a.ai_opportunity_score ?? 0;
  const qStatus = p.qualification_status || "unqualified";
  const qStatusLabel = {
    excellent: "Excellent", good: "Bon", medium: "Moyen", low: "Faible", unqualified: "Non qualifié",
  }[qStatus] || qStatus;
  const qStatusColor = {
    excellent: "bg-emerald-500 text-white",
    good: "bg-emerald-400 text-white",
    medium: "bg-amber-400 text-slate-900",
    low: "bg-slate-300 text-slate-700 dark:bg-slate-600 dark:text-slate-100",
    unqualified: "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-200",
  }[qStatus];
  const reasons = p.qualification_reasons || [];
  const verified = p.verified_fields || [];
  const unverified = p.unverified_fields || [];

  const changeStatus = async (status) => {
    await api.patch(`/prospects/${id}`, { status });
    toast.success("Statut mis à jour");
    load();
  };

  const generateMessage = async () => {
    setBusy(true); setGen(null);
    try {
      const { data } = await api.post("/messages/generate", { prospect_id: id, ...genOpts });
      setGen(data);
      toast.success("Message généré");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    } finally { setBusy(false); }
  };

  const sendMessage = async () => {
    if (!gen) return;
    setSending(true);
    try {
      const { data } = await api.post(`/messages/${gen.id}/send`);
      toast.success(data.test_mode ? "Envoi simulé (Test Mode)" : "Message envoyé");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    } finally { setSending(false); }
  };

  const addNote = async () => {
    if (!note.trim()) return;
    await api.post(`/prospects/${id}/notes`, { text: note });
    setNote("");
    toast.success("Note ajoutée");
    load();
  };

  const copyMsg = () => {
    const text = `${gen.subject ? gen.subject + "\n\n" : ""}${gen.body}\n\n${gen.cta || ""}`;
    navigator.clipboard.writeText(text);
    toast.success("Copié");
  };

  return (
    <div className="space-y-6">
      <Link to="/prospects" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="w-4 h-4" /> Retour
      </Link>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-semibold tracking-tight">{p.company_name}</h1>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline">{p.industry}</Badge>
                    <Badge variant="secondary">{p.city}, {p.canton}</Badge>
                    {(p.data_type === "demo" || p.is_demo) && <Badge className="text-[10px] bg-amber-500">DONNÉES SIMULÉES</Badge>}
                    {p.data_type === "test" && <Badge variant="destructive" className="text-[10px]">TEST</Badge>}
                    {p.data_type === "real" && <Badge className="text-[10px] bg-emerald-600">SOURCE RÉELLE</Badge>}
                    <Badge className={`text-[10px] ${qStatusColor}`}>{qStatusLabel}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-3">{p.description}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs text-muted-foreground">Score qualification</div>
                  <div className="text-4xl font-semibold tabular-nums">{score}</div>
                  <div className="text-xs text-muted-foreground">Confiance {p.qualification_confidence || 0}%</div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                {p.email && <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-muted-foreground" /> {p.email}</div>}
                {p.phone && <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-muted-foreground" /> {p.phone}</div>}
                {p.website && <div className="flex items-center gap-2"><Globe className="w-4 h-4 text-muted-foreground" /> <a href={p.website} target="_blank" rel="noreferrer" className="hover:underline truncate">{p.website}</a></div>}
                <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-muted-foreground" /> {p.address || "—"}, {p.postal_code} {p.city}</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                <h3 className="font-semibold">Détail du score</h3>
              </div>
              <p className="text-xs text-muted-foreground">
                Score calculé à partir de données vérifiables. Chaque point est explicable.
              </p>
              <div className="space-y-1.5">
                {reasons.length === 0 && <div className="text-sm text-muted-foreground">Aucun élément.</div>}
                {reasons.map((r, i) => (
                  <div key={i} data-testid={`score-reason-${i}`} className="flex items-start justify-between gap-3 text-sm py-1.5 border-b border-border last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{r.label}</div>
                      {r.evidence && <div className="text-xs text-muted-foreground truncate">{r.evidence}</div>}
                    </div>
                    <div className={`mono text-xs font-semibold shrink-0 ${r.delta >= 0 ? "text-emerald-600" : "text-destructive"}`}>
                      {r.delta >= 0 ? `+${r.delta}` : r.delta}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">Faits vs hypothèses</h3>
              </div>
              <div className="grid sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs uppercase text-emerald-600 font-semibold mb-1.5">Vérifié</div>
                  <div className="flex flex-wrap gap-1.5">
                    {verified.length === 0 && <div className="text-xs text-muted-foreground">Aucun</div>}
                    {verified.map((f) => (
                      <Badge key={f} variant="outline" className="text-[10px] border-emerald-400 text-emerald-700 dark:text-emerald-400">{f}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase text-amber-600 font-semibold mb-1.5">Hypothèse (IA)</div>
                  <div className="flex flex-wrap gap-1.5">
                    {unverified.length === 0 && <div className="text-xs text-muted-foreground">Aucun</div>}
                    {unverified.map((f) => (
                      <Badge key={f} variant="outline" className="text-[10px] border-amber-400 text-amber-700 dark:text-amber-400">{f}</Badge>
                    ))}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground pt-1">
                Les hypothèses ne sont pas des faits — vérifiez avant tout contact.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                <h3 className="font-semibold">Analyse IA</h3>
                {a.is_hypothesis && <Badge variant="secondary" className="text-[10px]">Hypothèse</Badge>}
              </div>
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-xs uppercase text-muted-foreground mb-1">Résumé</div>
                  <p>{a.summary || "—"}</p>
                </div>
                <div>
                  <div className="text-xs uppercase text-muted-foreground mb-1">Maturité numérique</div>
                  <p className="capitalize">{a.digital_maturity || "—"}</p>
                </div>
                <div>
                  <div className="text-xs uppercase text-muted-foreground mb-1">Opportunités</div>
                  <ul className="list-disc pl-5 space-y-0.5">{(a.opportunities || []).map((o, i) => <li key={i}>{o}</li>)}</ul>
                </div>
                <div>
                  <div className="text-xs uppercase text-muted-foreground mb-1">Automatisations IA utiles</div>
                  <ul className="list-disc pl-5 space-y-0.5">{(a.ai_use_cases || []).map((o, i) => <li key={i}>{o}</li>)}</ul>
                </div>
                <div className="md:col-span-2">
                  <div className="text-xs uppercase text-muted-foreground mb-1">Arguments commerciaux</div>
                  <ul className="list-disc pl-5 space-y-0.5">{(a.sales_arguments || []).map((o, i) => <li key={i}>{o}</li>)}</ul>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Générer une approche commerciale</h3>
                <Badge variant="outline" className="text-[10px]">IA</Badge>
              </div>
              <Tabs value={genOpts.channel} onValueChange={(v) => setGenOpts({...genOpts, channel: v})}>
                <TabsList>
                  <TabsTrigger data-testid="tab-email" value="email">Email</TabsTrigger>
                  <TabsTrigger value="phone">Téléphone</TabsTrigger>
                  <TabsTrigger value="linkedin">LinkedIn</TabsTrigger>
                  <TabsTrigger value="whatsapp">WhatsApp</TabsTrigger>
                </TabsList>
                <TabsContent value={genOpts.channel} className="space-y-4 pt-4">
                  <div className="grid md:grid-cols-5 gap-3">
                    <div><Label>Style</Label>
                      <Select value={genOpts.strategy} onValueChange={(v) => setGenOpts({...genOpts, strategy: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="direct_short">Direct & court</SelectItem>
                          <SelectItem value="professional">Professionnel</SelectItem>
                          <SelectItem value="consultative">Consultatif</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div><Label>Ton</Label>
                      <Select value={genOpts.tone} onValueChange={(v) => setGenOpts({...genOpts, tone: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {["très professionnel","professionnel","humain","décontracté","direct","premium"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div><Label>Longueur</Label>
                      <Select value={genOpts.length} onValueChange={(v) => setGenOpts({...genOpts, length: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{["très court","court","normal"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Langue</Label>
                      <Select value={genOpts.language} onValueChange={(v) => setGenOpts({...genOpts, language: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {["auto","fr","de","it","en","es"].map((s) => <SelectItem key={s} value={s}>{s.toUpperCase()}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div><Label>Objectif</Label>
                      <Select value={genOpts.objective} onValueChange={(v) => setGenOpts({...genOpts, objective: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="presentation">Présentation</SelectItem>
                          <SelectItem value="audit">Proposer un audit</SelectItem>
                          <SelectItem value="demo">Démonstration</SelectItem>
                          <SelectItem value="call">Appel</SelectItem>
                          <SelectItem value="trial">Essai</SelectItem>
                          <SelectItem value="interest">Intérêt général</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <Button data-testid="generate-message" onClick={generateMessage} disabled={busy}>
                    {busy ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Génération…</> : <><Sparkles className="w-4 h-4 mr-1.5" /> Générer le message</>}
                  </Button>
                  {gen && (
                    <div className="space-y-2 border-t border-border pt-4">
                      {gen.subject && (
                        <div className="space-y-1"><Label>Objet</Label>
                          <Input value={gen.subject} onChange={(e) => setGen({...gen, subject: e.target.value})} />
                        </div>
                      )}
                      <div className="space-y-1"><Label>Message</Label>
                        <Textarea data-testid="generated-message-body" rows={8} value={gen.body} onChange={(e) => setGen({...gen, body: e.target.value})} />
                      </div>
                      {gen.cta && (
                        <div className="space-y-1"><Label>Call-to-action</Label>
                          <Input value={gen.cta} onChange={(e) => setGen({...gen, cta: e.target.value})} />
                        </div>
                      )}
                      <div className="flex gap-2 pt-2">
                        <Button variant="outline" onClick={copyMsg}><Copy className="w-4 h-4 mr-1.5" />Copier</Button>
                        <Button variant="outline" onClick={async () => {
                          await api.patch(`/messages/${gen.id}`, { subject: gen.subject, body: gen.body, cta: gen.cta, status: "approved" });
                          toast.success("Message approuvé");
                        }}><CheckCircle className="w-4 h-4 mr-1.5" />Approuver</Button>
                        <Button data-testid="send-message" onClick={sendMessage} disabled={sending}>
                          <Send className="w-4 h-4 mr-1.5" />{sending ? "…" : "Envoyer"}
                        </Button>
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <Card>
            <CardContent className="p-6 space-y-3">
              <h3 className="font-semibold">Statut</h3>
              <Select value={p.status} onValueChange={changeStatus}>
                <SelectTrigger data-testid="prospect-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="space-y-1 text-xs text-muted-foreground">
                <div>Provider : {p.source_provider || p.source}</div>
                <div>Type : {p.data_type === "real" ? "Source réelle" : p.data_type === "test" ? "Test" : "Données simulées"}</div>
                {p.retrieved_at && <div>Récupéré : {new Date(p.retrieved_at).toLocaleString()}</div>}
                {p.source_url && <a className="underline" href={p.source_url} target="_blank" rel="noreferrer">Ouvrir la source</a>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <h3 className="font-semibold">Notes</h3>
              <Textarea rows={3} placeholder="Ajouter une note..." value={note} onChange={(e) => setNote(e.target.value)} />
              <Button size="sm" onClick={addNote}>Ajouter</Button>
              <div className="space-y-2 pt-2">
                {(p.notes || []).map((n) => (
                  <div key={n.id} className="text-sm p-2 rounded-md bg-accent/40">
                    <div className="text-[11px] text-muted-foreground">{n.author} — {new Date(n.at).toLocaleString()}</div>
                    <div>{n.text}</div>
                  </div>
                ))}
                {(!p.notes || p.notes.length === 0) && <div className="text-xs text-muted-foreground">Aucune note.</div>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-3">
              <h3 className="font-semibold">Historique messages</h3>
              {messages.length === 0 && <div className="text-xs text-muted-foreground">Aucun message.</div>}
              {messages.map((m) => (
                <div key={m.id} className="text-sm p-3 rounded-md border border-border">
                  <div className="flex items-center justify-between mb-1">
                    <Badge variant="outline" className="text-[10px] uppercase">{m.channel}</Badge>
                    <Badge variant={m.status === "sent" ? "default" : "secondary"} className="text-[10px]">{m.status}</Badge>
                  </div>
                  {m.subject && <div className="font-medium text-sm">{m.subject}</div>}
                  <div className="text-xs text-muted-foreground line-clamp-3">{m.body}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
