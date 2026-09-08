"""Aura V8 Opportunity Intelligence.
Rule-based and explainable: it never invents prospect facts.
The output is designed to be useful even before a paid LLM is connected.
"""
from __future__ import annotations
from typing import Optional
from urllib.parse import urlparse
import re


def _clamp(v:int, lo:int=0, hi:int=100)->int:
    return max(lo, min(hi, int(v)))


def _norm(v: Optional[str])->str:
    return re.sub(r"\s+", " ", (v or "").strip().lower())


def build_opportunity(prospect: dict, services_to_sell: list[str] | None = None, offer: dict | None = None) -> dict:
    services_to_sell = services_to_sell or []
    offer = offer or {}
    verification = int(prospect.get("verification_score") or 0)
    has_site = bool(prospect.get("website"))
    has_email = bool(prospect.get("email"))
    has_phone = bool(prospect.get("phone"))
    has_year = bool(prospect.get("founded_year"))
    business_domain = prospect.get("business_domain") or prospect.get("industry") or ""
    description = prospect.get("description") or ""
    ai = prospect.get("ai_analysis") or {}

    # Data quality is factual and auditable.
    data_quality = 20
    data_quality += min(45, verification // 2)
    data_quality += 12 if has_site else 0
    data_quality += 10 if has_email else 0
    data_quality += 8 if has_phone else 0
    data_quality += 5 if has_year else 0
    data_quality = _clamp(data_quality)

    contactability = 15 + (35 if has_email else 0) + (25 if has_phone else 0) + (15 if has_site else 0)
    if prospect.get("do_not_contact") or prospect.get("opted_out"):
        contactability = 0
    contactability = _clamp(contactability)

    # Fit: requested offer/service versus verified prospect domain/activity.
    offer_blob = " ".join([str(x) for x in services_to_sell] + [
        offer.get("product_name") or "", offer.get("description") or "", offer.get("target_customer") or ""
    ])
    target_blob = f"{business_domain} {prospect.get('industry') or ''} {description}"
    offer_tokens = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", _norm(offer_blob))}
    target_tokens = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", _norm(target_blob))}
    overlap = len(offer_tokens & target_tokens)
    fit = 48 + min(24, overlap * 6)
    if verification >= 60: fit += 8
    if prospect.get("professional_relevance"): fit += 5
    fit = _clamp(fit)

    # Need score uses only observable signals, with hypotheses clearly separated.
    need = 35
    why=[]
    observations=[]
    if has_site:
        observations.append("Site officiel identifié")
        need += 4
    else:
        why.append("Aucun site officiel identifié dans les données disponibles")
        need += 8
    if has_email:
        observations.append("Adresse e-mail professionnelle disponible")
    if has_phone:
        observations.append("Téléphone professionnel disponible")
    if has_year:
        y=int(prospect.get("founded_year"))
        observations.append(f"Année de création indiquée : {y}")
        if y >= 2021:
            need += 8
            why.append("Entreprise relativement récente : potentiel besoin de structuration/croissance à vérifier")
    for opp in (ai.get("opportunities") or [])[:2]:
        # AI opportunity remains explicitly a hypothesis, never a fact.
        why.append(f"Hypothèse à vérifier : {opp}")
        need += 4
    need = _clamp(need)

    commercial = round(fit*.34 + need*.26 + data_quality*.22 + contactability*.18)
    commercial = _clamp(commercial)
    if commercial >= 85: grade="A+"
    elif commercial >= 75: grade="A"
    elif commercial >= 65: grade="B"
    elif commercial >= 50: grade="C"
    else: grade="D"

    if not why:
        why.append(f"Correspond au domaine {business_domain or 'recherché'}")
        if verification:
            why.append(f"Identité/données vérifiées à {verification}%")
        if has_email or has_phone:
            why.append("Canal de contact professionnel disponible")
    why=why[:4]

    return {
        "fit_score": fit,
        "need_score": need,
        "data_quality_score": data_quality,
        "contactability_score": contactability,
        "commercial_score": commercial,
        "aura_grade": grade,
        "why_this_prospect": why,
        "verified_observations": observations[:6],
        "message_context": {
            "company_name": prospect.get("company_name"),
            "business_domain": business_domain,
            "city": prospect.get("city"),
            "founded_year": prospect.get("founded_year"),
            "verified_observations": observations[:6],
            "why": why,
        },
        "engine_version": "v8.0",
    }
