"""AI service - explainable prospect qualification + message generation.

Fully mockable via Test Mode. Never blocks on external calls in demo runs.
The qualification score is computed deterministically with reason breakdown,
so users understand WHY a prospect received a given score.
"""
from __future__ import annotations
import os
import json
import re
from typing import Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage

GENERIC_EMAIL_PREFIXES = ("info@", "contact@", "office@", "hello@", "admin@", "support@")
PERSONAL_EMAIL_DOMAINS = ("gmail.com", "hotmail.com", "yahoo.com", "bluewin.ch", "outlook.com", "live.com")

VERIFIABLE_FIELDS = ("company_name", "industry", "website", "email", "phone",
                      "address", "postal_code", "city", "canton", "country")


def _client(session_id: str, system: str, model: str = "gpt-5.4") -> LlmChat:
    key = os.environ["EMERGENT_LLM_KEY"]
    return LlmChat(api_key=key, session_id=session_id, system_message=system).with_model("openai", model)


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def compute_qualification(prospect: dict, services_to_sell: list[str] | None = None,
                           min_score: int = 0) -> dict:
    """Deterministic, explainable qualification scoring.

    Returns dict with: qualification_score, qualification_status,
    qualification_confidence, qualification_reasons (list of {delta,label,evidence}),
    verified_fields, unverified_fields.
    """
    reasons: list[dict] = []
    score = 40  # baseline

    # ---- Verifiable evidence-based points ----
    if prospect.get("industry"):
        reasons.append({"delta": 15, "label": "Secteur cible identifié",
                        "evidence": f"Catégorie: {prospect.get('industry')}"})
        score += 15
    if prospect.get("city") or prospect.get("canton"):
        reasons.append({"delta": 10, "label": "Localisation vérifiée",
                        "evidence": f"{prospect.get('city') or ''} {prospect.get('canton') or ''}".strip()})
        score += 10
    if prospect.get("website"):
        reasons.append({"delta": 15, "label": "Site internet valide",
                        "evidence": prospect.get("website")})
        score += 15
    if prospect.get("email"):
        email = prospect["email"].lower()
        if any(email.startswith(p) for p in GENERIC_EMAIL_PREFIXES):
            reasons.append({"delta": 5, "label": "Email générique disponible",
                            "evidence": "Email de type contact@/info@ — moins direct"})
            score += 5
        elif any(d in email for d in PERSONAL_EMAIL_DOMAINS):
            reasons.append({"delta": 3, "label": "Email personnel (peu recommandé)",
                            "evidence": "Domaine grand public"})
            score += 3
        else:
            reasons.append({"delta": 10, "label": "Email professionnel disponible",
                            "evidence": email})
            score += 10
    if prospect.get("phone"):
        reasons.append({"delta": 5, "label": "Téléphone disponible",
                        "evidence": prospect.get("phone")})
        score += 5

    # ---- Service alignment (context) ----
    if services_to_sell:
        reasons.append({"delta": 5, "label": "Service ciblé pertinent",
                        "evidence": ", ".join(services_to_sell[:2])})
        score += 5

    # ---- Penalties ----
    if not prospect.get("website"):
        reasons.append({"delta": -5, "label": "Aucun site internet",
                        "evidence": "Difficile à qualifier sans présence en ligne"})
        score -= 5
    if not prospect.get("email") and not prospect.get("phone"):
        reasons.append({"delta": -10, "label": "Aucun canal de contact vérifié",
                        "evidence": "Ni email ni téléphone"})
        score -= 10
    if prospect.get("do_not_contact"):
        reasons.append({"delta": -100, "label": "Sur liste 'ne pas contacter'",
                        "evidence": "Ce prospect a demandé à ne plus être contacté"})
        score = 0
    if prospect.get("opted_out"):
        reasons.append({"delta": -100, "label": "Opt-out enregistré",
                        "evidence": "Désinscription formelle"})
        score = 0

    score = max(0, min(100, score))

    if score < 40:
        qstatus = "low"
    elif score < 60:
        qstatus = "medium"
    elif score < 80:
        qstatus = "good"
    else:
        qstatus = "excellent"

    if score < min_score:
        qstatus = "unqualified"

    # Confidence: how much of what we know is actually verifiable
    verified = [f for f in VERIFIABLE_FIELDS if prospect.get(f)]
    unverified = ["decision_maker", "employee_count", "revenue", "problems", "technology_stack"]
    confidence = int(min(95, 20 + len(verified) * 8))

    return {
        "qualification_score": score,
        "qualification_status": qstatus,
        "qualification_confidence": confidence,
        "qualification_reasons": reasons,
        "verified_fields": verified,
        "unverified_fields": unverified,
    }


async def analyze_prospect(prospect: dict, services_to_sell: list[str], test_mode: bool = True,
                            model: str = "gpt-5.4") -> dict:
    """Return AIAnalysis-shaped dict. Test Mode does not force fake analysis."""
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return _mock_analysis(prospect, services_to_sell)

    services_str = ", ".join(services_to_sell) if services_to_sell else "prospection IA"
    system = (
        "Tu es un analyste commercial B2B expert. Réponds uniquement en JSON valide, "
        "sans texte avant ni après. Toutes les hypothèses doivent être marquées."
    )
    prompt = f"""Analyse cette entreprise pour de la prospection commerciale.

Entreprise: {prospect.get('company_name')}
Secteur: {prospect.get('industry')}
Ville: {prospect.get('city')} ({prospect.get('canton')})
Site: {prospect.get('website') or 'inconnu'}
Description: {prospect.get('description') or 'inconnue'}

Services à vendre: {services_str}

Réponds en JSON avec ces clés (JSON strict, jamais de champs inventés en fait):
{{
  "summary": "résumé 2 phrases (hypothèse)",
  "main_activity": "activité principale",
  "services": ["service1", "service2"],
  "likely_customers": "clientèle probable (hypothèse)",
  "digital_maturity": "faible|moyenne|forte",
  "opportunities": ["opp1"],
  "problems": ["problème potentiel"],
  "ai_use_cases": ["cas1"],
  "sales_arguments": ["argument1"],
  "relevance_note": "pourquoi ce prospect pourrait être pertinent",
  "confidence_score": 0-100
}}"""
    try:
        chat = _client(f"analyze-{prospect.get('id', 'x')}", system, model)
        resp = await chat.send_message(UserMessage(text=prompt))
        data = _extract_json(resp if isinstance(resp, str) else str(resp))
        if not data:
            return _mock_analysis(prospect, services_to_sell)
        data["confidence_score"] = int(data.get("confidence_score", 50) or 50)
        data["is_hypothesis"] = True
        return data
    except Exception:
        return _mock_analysis(prospect, services_to_sell)


def _mock_analysis(prospect: dict, services_to_sell: list[str]) -> dict:
    industry = (prospect.get("industry") or "").lower()
    city = prospect.get("city") or "la région"
    has_site = bool(prospect.get("website"))
    return {
        "summary": f"{prospect.get('company_name')} pourrait être un acteur {industry} implanté à {city}. Hypothèse basée sur les données disponibles.",
        "main_activity": prospect.get("industry") or "Services",
        "services": [f"{industry.title()} général", "Interventions ciblées"],
        "likely_customers": "Particuliers et PME locales (hypothèse)",
        "digital_maturity": "moyenne" if has_site else "faible",
        "opportunities": [
            "Site web modernisable" if has_site else "Absence de site web",
            "Communication client à automatiser",
        ],
        "problems": ["Réponse aux demandes clients potentiellement lente (hypothèse)"],
        "ai_use_cases": ["Réponses automatiques", "Qualification leads entrants"],
        "sales_arguments": [
            f"Gain de temps estimé pour {prospect.get('company_name')}",
            f"Adapté aux entreprises {industry} de taille similaire",
        ],
        "relevance_note": "Analyse générée en mode démonstration. Toutes les conclusions sont des hypothèses.",
        "confidence_score": 55,
        "is_hypothesis": True,
    }


async def generate_message(prospect: dict, channel: str, tone: str, length: str,
                            language: str, objective: str, service_notes: Optional[str],
                            test_mode: bool = True, model: str = "gpt-5.4",
                            offer: Optional[dict] = None, strategy: str = "professional") -> dict:
    """Generate a high-quality B2B draft.

    Test Mode does NOT disable draft generation; it only blocks outbound sending elsewhere.
    Missing LLM credentials fall back to a professional deterministic draft.
    """
    offer = offer or {}
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return _fallback_message(prospect, channel, language, offer, service_notes, strategy)

    known = {
        "company_name": prospect.get("company_name"),
        "industry": prospect.get("industry"),
        "city": prospect.get("city"),
        "canton": prospect.get("canton"),
        "website": prospect.get("website"),
        "phone": prospect.get("phone"),
        "source_provider": prospect.get("source_provider"),
    }
    offer_text = {
        "product_name": offer.get("product_name") or "Aura Hub / Prospect AI",
        "description": offer.get("description") or service_notes or "outil de prospection B2B assisté par IA",
        "main_benefit": offer.get("main_benefit") or "réduire le temps nécessaire pour identifier et qualifier de nouvelles opportunités commerciales",
        "target_customer": offer.get("target_customer"),
        "price": offer.get("price"),
        "special_offer": offer.get("special_offer"),
        "differentiator": offer.get("differentiator") or "la recherche, la qualification et la préparation de prises de contact sont réunies dans un même flux",
        "cta_preference": offer.get("cta_preference") or "send_example",
        "sender_name": offer.get("sender_name") or "Bryan",
        "brand": offer.get("brand") or "Aura Hub",
        "signature": offer.get("signature"),
        "website": offer.get("website"),
    }

    system = (
        "Tu es un excellent commercial B2B francophone, sobre et crédible. "
        "Tu rédiges des prises de contact qui ressemblent à un humain expérimenté, pas à une IA. "
        "N'invente jamais un problème, un chiffre, un dirigeant ou une information non fournie. "
        "Si une information n'est pas vérifiée, formule-la comme une possibilité générale au secteur, jamais comme un fait sur l'entreprise. "
        "Évite les clichés marketing (révolutionner, booster, monde en constante évolution). "
        "Le message doit être facile à lire et facile à répondre. Réponds uniquement en JSON strict."
    )
    prompt = f"""Rédige un brouillon de prospection B2B.

DONNÉES VÉRIFIÉES / SOURCE:
{json.dumps(known, ensure_ascii=False)}

OFFRE DU VENDEUR:
{json.dumps(offer_text, ensure_ascii=False)}

PARAMÈTRES:
Canal: {channel}
Stratégie: {strategy}
Ton: {tone}
Longueur: {length}
Langue: {language}
Objectif: {objective}

RÈGLES:
- Pour un email, vise environ 70 à 140 mots sauf demande explicite contraire.
- Commence par une accroche contextuelle fondée seulement sur les données fournies.
- Explique clairement pourquoi le contact est pertinent et la valeur proposée.
- Ne prétends jamais avoir audité les processus internes du prospect.
- CTA faible friction: demander l'autorisation d'envoyer un exemple ou de montrer une courte démo.
- Si l'offre est Aura Hub et que la source_provider est réelle, tu peux mentionner une seule fois que l'outil a aidé à identifier l'entreprise, sans en faire un gimmick forcé.
- Fournis 3 objets d'email professionnels et non-spammy si canal=email.

JSON attendu:
{{
  "subject": "meilleur objet",
  "subject_options": ["objet1", "objet2", "objet3"],
  "body": "message complet",
  "cta": "CTA court"
}}"""
    try:
        chat = _client(f"msg-{prospect.get('id', 'x')}", system, model)
        resp = await chat.send_message(UserMessage(text=prompt))
        data = _extract_json(resp if isinstance(resp, str) else str(resp))
        if not data or "body" not in data:
            return _fallback_message(prospect, channel, language, offer, service_notes, strategy)
        if not data.get("subject_options") and data.get("subject"):
            data["subject_options"] = [data["subject"]]
        return data
    except Exception:
        return _fallback_message(prospect, channel, language, offer, service_notes, strategy)


def _fallback_message(prospect: dict, channel: str, language: str, offer: dict,
                      service_notes: Optional[str], strategy: str) -> dict:
    """Professional non-LLM fallback. Never fabricates prospect-specific problems."""
    name = prospect.get("company_name") or "votre entreprise"
    city = prospect.get("city")
    industry = prospect.get("industry") or "votre secteur"
    product = offer.get("product_name") or "Aura Hub"
    description = offer.get("description") or service_notes or "un outil de prospection B2B assisté par IA"
    benefit = offer.get("main_benefit") or "identifier et qualifier plus rapidement de nouvelles opportunités commerciales"
    sender = offer.get("sender_name") or "Bryan"
    brand = offer.get("brand") or "Aura Hub"
    signature = offer.get("signature") or f"{sender}\n{brand}"
    real_source = (prospect.get("data_type") == "real" and prospect.get("source_provider") not in (None, "mock", "demo"))

    context = f"dans le domaine {industry}" + (f" à {city}" if city else "")
    self_proof = ""
    if product.lower().startswith("aura") and real_source:
        self_proof = " C'est d'ailleurs Aura qui m'a aidé à identifier votre entreprise dans le cadre de cette recherche."

    if channel == "email":
        subjects = [
            f"Une idée pour la prospection de {name}",
            f"Question concernant {name}",
            f"Une piste commerciale pour {name}",
        ]
        if strategy == "direct_short":
            body = (
                f"Bonjour,\n\nJe me permets de vous contacter car {name} est actif {context}. "
                f"Je développe {product}, {description}. L'objectif est simple : {benefit}.{self_proof}\n\n"
                f"Si le sujet vous parle, est-ce que je peux vous envoyer un exemple concret adapté à votre activité ?\n\n"
                f"Cordialement,\n{signature}"
            )
        elif strategy == "consultative":
            body = (
                f"Bonjour,\n\nJe me permets de vous écrire car {name} est actif {context}. "
                f"Je travaille sur {product}, {description}, avec l'objectif de {benefit}. "
                f"Je ne présume pas de votre organisation actuelle ; je cherche surtout à voir dans quels contextes l'outil apporte une vraie valeur.{self_proof}\n\n"
                f"Est-ce que je peux vous envoyer un exemple très concret de ce que cela pourrait donner pour votre activité ?\n\n"
                f"Cordialement,\n{signature}"
            )
        else:
            body = (
                f"Bonjour,\n\nJe me permets de vous contacter car {name} est actif {context}. "
                f"Je développe {product}, {description}. Il est conçu pour {benefit}, tout en gardant la validation humaine avant les prises de contact.{self_proof}\n\n"
                f"Je cherche actuellement quelques entreprises à qui montrer le fonctionnement sur un cas concret. "
                f"Est-ce que je peux vous envoyer un exemple adapté à votre activité ?\n\n"
                f"Cordialement,\n{signature}"
            )
        return {"subject": subjects[0], "subject_options": subjects, "body": body,
                "cta": "Est-ce que je peux vous envoyer un exemple concret ?"}

    body = (f"Bonjour, je vous contacte car {name} est actif {context}. "
            f"Je développe {product}, {description}, pour {benefit}. "
            f"Est-ce que je peux vous montrer un exemple concret ?")
    return {"subject": None, "subject_options": [], "body": body,
            "cta": "Montrer un exemple concret"}
