"""Aura Phase 1 Commercial — Opportunity Intelligence V2.

Explainable, conservative commercial scoring. It separates verified observations
from hypotheses and never converts an AI hypothesis into a factual claim.
"""
from __future__ import annotations
from typing import Optional
import re


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(v))))


def _norm(v: Optional[str]) -> str:
    value = re.sub(r"\s+", " ", (v or "").strip().lower())
    table = str.maketrans({
        "é":"e", "è":"e", "ê":"e", "ë":"e", "à":"a", "â":"a", "ä":"a",
        "ö":"o", "ô":"o", "ü":"u", "û":"u", "î":"i", "ï":"i", "ç":"c",
    })
    return value.translate(table)


def _tokens(v: str) -> set[str]:
    stop = {"avec","dans","pour","les","des","une","un","de","du","la","le","et","aux","sur","service","services","entreprise","societe"}
    return {w for w in re.findall(r"[a-z0-9]{3,}", _norm(v)) if w not in stop}


def _matches_requested_domain(prospect: dict, search_context: dict) -> tuple[bool, str]:
    requested = _norm(search_context.get("industry") or "")
    actual = _norm(prospect.get("business_domain") or prospect.get("industry") or "")
    if not requested:
        return True, ""
    rt = _tokens(requested)
    at = _tokens(actual)
    if requested in actual or actual in requested or bool(rt & at):
        return True, requested
    # The provider may normalize painter -> construction/artisanat etc.; industry still carries request.
    p_industry = _norm(prospect.get("industry") or "")
    if requested in p_industry or bool(rt & _tokens(p_industry)):
        return True, requested
    return False, requested


def build_opportunity(
    prospect: dict,
    services_to_sell: list[str] | None = None,
    offer: dict | None = None,
    search_context: dict | None = None,
) -> dict:
    services_to_sell = services_to_sell or []
    offer = offer or {}
    search_context = search_context or {}

    verification = int(prospect.get("verification_score") or 0)
    has_site = bool(prospect.get("website"))
    has_email = bool(prospect.get("email"))
    has_phone = bool(prospect.get("phone"))
    has_year = isinstance(prospect.get("founded_year"), int)
    business_domain = prospect.get("business_domain") or prospect.get("industry") or ""
    ai = prospect.get("ai_analysis") or {}

    observations: list[str] = []
    hypotheses: list[str] = []
    signals: list[dict] = []

    # ---------- Data quality ----------
    data_quality = 15 + min(50, verification // 2)
    if has_site:
        data_quality += 12
        observations.append("Site officiel identifié")
        signals.append({"type":"data", "label":"Site officiel identifié", "evidence":prospect.get("website"), "confidence":95, "is_hypothesis":False})
    if has_email:
        data_quality += 10
        observations.append("Adresse e-mail professionnelle disponible")
        signals.append({"type":"contact", "label":"E-mail disponible", "evidence":prospect.get("email"), "confidence":95, "is_hypothesis":False})
    if has_phone:
        data_quality += 8
        observations.append("Téléphone professionnel disponible")
        signals.append({"type":"contact", "label":"Téléphone disponible", "evidence":prospect.get("phone"), "confidence":95, "is_hypothesis":False})
    if has_year:
        data_quality += 5
        observations.append(f"Année de création indiquée : {prospect.get('founded_year')}")
        signals.append({"type":"company", "label":"Ancienneté connue", "evidence":str(prospect.get("founded_year")), "confidence":int(prospect.get("founded_year_confidence") or 75), "is_hypothesis":False})
    data_quality = _clamp(data_quality)

    # ---------- Contactability ----------
    contactability = 10 + (42 if has_email else 0) + (27 if has_phone else 0) + (12 if has_site else 0)
    if prospect.get("do_not_contact") or prospect.get("opted_out"):
        contactability = 0
    contactability = _clamp(contactability)

    # ---------- Fit to the user's actual search target ----------
    fit = 38
    domain_match, requested = _matches_requested_domain(prospect, search_context)
    if requested:
        if domain_match:
            fit += 34
            observations.append(f"Activité cohérente avec la cible recherchée : {search_context.get('industry')}")
            signals.append({"type":"fit", "label":"Activité cible correspondante", "evidence":business_domain or prospect.get("industry"), "confidence":90, "is_hypothesis":False})
        else:
            fit -= 25
            hypotheses.append("L'activité semble moins alignée avec la cible demandée — à vérifier")
    if search_context.get("city") and _norm(prospect.get("city")) == _norm(search_context.get("city")):
        fit += 10
        observations.append(f"Localisation correspondant à la zone cible : {prospect.get('city')}")
    elif search_context.get("canton") and _norm(prospect.get("canton")) == _norm(search_context.get("canton")):
        fit += 6
    if verification >= 70:
        fit += 7
    if prospect.get("professional_relevance"):
        fit += 4
    fit = _clamp(fit)

    # ---------- Need / opportunity signals ----------
    # This does NOT claim the prospect has a problem. It estimates commercial opportunity
    # from observable public signals and explicitly-labelled hypotheses.
    need = 32
    if not has_site:
        need += 12
        hypotheses.append("Absence de site officiel identifié : potentiel besoin de visibilité/structuration à vérifier")
        signals.append({"type":"opportunity", "label":"Aucun site officiel identifié", "evidence":"Données disponibles", "confidence":70, "is_hypothesis":True})
    else:
        need += 3
    if has_year:
        year = int(prospect.get("founded_year"))
        if year >= 2022:
            need += 10
            hypotheses.append("Entreprise récente : des besoins de structuration ou d'acquisition peuvent exister")
            signals.append({"type":"opportunity", "label":"Entreprise récente", "evidence":str(year), "confidence":75, "is_hypothesis":True})
        elif year <= 2005:
            need += 4
            hypotheses.append("Entreprise établie : potentiel d'optimisation de processus à évaluer")
    if has_email and (prospect.get("email") or "").lower().startswith(("info@", "contact@", "office@", "admin@")):
        need += 4
        signals.append({"type":"opportunity", "label":"Point de contact générique", "evidence":prospect.get("email"), "confidence":85, "is_hypothesis":True})

    for opp in (ai.get("opportunities") or [])[:3]:
        if not opp:
            continue
        need += 4
        label = f"Hypothèse IA à vérifier : {opp}"
        hypotheses.append(label)
        signals.append({"type":"ai_hypothesis", "label":str(opp), "evidence":"Analyse IA", "confidence":int(ai.get("confidence_score") or 50), "is_hypothesis":True})
    need = _clamp(need)

    # ---------- Commercial priority ----------
    commercial = _clamp(fit * 0.36 + need * 0.24 + data_quality * 0.22 + contactability * 0.18)
    if commercial >= 88:
        grade, priority = "A+", "Très haute"
    elif commercial >= 78:
        grade, priority = "A", "Haute"
    elif commercial >= 66:
        grade, priority = "B", "Bonne"
    elif commercial >= 52:
        grade, priority = "C", "À analyser"
    else:
        grade, priority = "D", "Faible"

    # ---------- Recommended commercial angle ----------
    product = offer.get("product_name") or (services_to_sell[0] if services_to_sell else "votre offre")
    benefit = offer.get("main_benefit") or "gagner du temps et structurer l'acquisition commerciale"
    if has_year and int(prospect.get("founded_year")) >= 2022:
        angle = f"Croissance / structuration : montrer comment {product} peut aider à {benefit}."
    elif contactability >= 70 and fit >= 70:
        angle = f"Approche très ciblée : relier {product} à un bénéfice concret pour une entreprise de ce secteur."
    elif has_site:
        angle = f"Approche consultative : partir d'un élément vérifiable de l'activité et présenter {product} sans supposer de problème."
    else:
        angle = f"Approche découverte : valider d'abord le besoin avant de présenter {product}."

    if prospect.get("do_not_contact") or prospect.get("opted_out"):
        next_action = "Ne pas contacter — restriction enregistrée."
    elif verification < 45:
        next_action = "Revérifier l'entreprise avant de préparer un message."
    elif not has_email and not has_phone:
        next_action = "Enrichir les coordonnées avant prise de contact."
    elif commercial >= 78:
        next_action = "Préparer une approche personnalisée et la soumettre à validation."
    else:
        next_action = "Analyser la fiche avant de décider d'une prise de contact."

    why: list[str] = []
    for item in observations:
        if item not in why:
            why.append(item)
        if len(why) >= 3:
            break
    for item in hypotheses:
        if item not in why:
            why.append(item)
        if len(why) >= 4:
            break
    if not why:
        why.append(f"Correspondance potentielle avec le domaine {business_domain or 'recherché'}")

    return {
        "fit_score": fit,
        "need_score": need,
        "data_quality_score": data_quality,
        "contactability_score": contactability,
        "commercial_score": commercial,
        "priority_score": commercial,
        "priority_label": priority,
        "aura_grade": grade,
        "why_this_prospect": why[:4],
        "verified_observations": observations[:8],
        "hypotheses": hypotheses[:6],
        "sales_signals": signals[:10],
        "recommended_angle": angle,
        "next_best_action": next_action,
        "message_context": {
            "company_name": prospect.get("company_name"),
            "business_domain": business_domain,
            "city": prospect.get("city"),
            "founded_year": prospect.get("founded_year"),
            "verified_observations": observations[:6],
            "hypotheses": hypotheses[:4],
            "recommended_angle": angle,
        },
        "engine_version": "commercial-v2.0",
    }
