"""Phase 1 Commercial — Mission Mode + clone profile helpers.

Mission parsing is intentionally safe:
- no search is launched automatically;
- the result is only a pre-filled SearchCriteria proposal;
- OpenAI is optional; deterministic parsing works without a key;
- no company facts are invented.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional



CITY_CANTON = {
    "lausanne": "VD", "morges": "VD", "cossonay": "VD", "nyon": "VD",
    "vevey": "VD", "montreux": "VD", "yverdon": "VD", "yverdon-les-bains": "VD",
    "genève": "GE", "geneve": "GE", "carouge": "GE",
    "fribourg": "FR", "bulle": "FR", "neuchâtel": "NE", "neuchatel": "NE",
    "sion": "VS", "martigny": "VS", "berne": "BE", "bern": "BE",
    "bienne": "BE", "zurich": "ZH", "zürich": "ZH", "bâle": "BS", "basel": "BS",
    "lucerne": "LU", "luzern": "LU", "lugano": "TI", "bellinzone": "TI",
}

CANTON_NAMES = {
    "vaud": "VD", "genève": "GE", "geneve": "GE", "fribourg": "FR",
    "neuchâtel": "NE", "neuchatel": "NE", "valais": "VS", "berne": "BE",
    "bern": "BE", "zurich": "ZH", "zürich": "ZH", "bâle": "BS", "basel": "BS",
    "lucerne": "LU", "tessin": "TI", "ticino": "TI",
}

DOMAIN_ALIASES = {
    "administration": "Administratif", "administratif": "Administratif", "secrétariat": "Administratif",
    "secretariat": "Administratif", "back office": "Administratif", "assistant administratif": "Administratif",
    "informatique": "Informatique", "it": "Informatique", "infogérance": "Informatique", "infogerance": "Informatique",
    "électricien": "Électricien", "electricien": "Électricien", "électricité": "Électricien", "electricite": "Électricien",
    "peintre": "Peintre", "peinture": "Peintre", "plombier": "Plombier / chauffage", "plomberie": "Plombier / chauffage",
    "chauffage": "Plombier / chauffage", "fiduciaire": "Fiduciaire / comptabilité", "comptabilité": "Fiduciaire / comptabilité",
    "comptabilite": "Fiduciaire / comptabilité", "marketing": "Marketing / communication", "communication": "Marketing / communication",
    "immobilier": "Immobilier", "restaurant": "Restaurant / hôtellerie", "restauration": "Restaurant / hôtellerie",
    "hôtel": "Restaurant / hôtellerie", "hotel": "Restaurant / hôtellerie", "santé": "Santé / bien-être",
    "sante": "Santé / bien-être", "bien-être": "Santé / bien-être", "animaux": "Animaux", "animal": "Animaux",
    "garage": "Garage / automobile", "automobile": "Garage / automobile", "architecte": "Architecte",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _heuristic_parse(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    low = _norm(raw)

    industry = ""
    for alias, canonical in sorted(DOMAIN_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if alias in low:
            industry = canonical
            break

    city = None
    canton = None
    for name, c in sorted(CITY_CANTON.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", low):
            city = name.title().replace("Geneve", "Genève").replace("Neuchatel", "Neuchâtel")
            canton = c
            break
    for name, code in CANTON_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            canton = code
            break

    max_results = 20
    m = re.search(r"\b(\d{1,3})\s+(?:entreprises?|prospects?|sociétés?|societes?|pmes?)\b", low)
    if m:
        max_results = max(1, min(50, int(m.group(1))))

    filters: dict[str, Any] = {
        "has_website": "any", "has_email": "any", "has_phone": "any",
        "business_domain": "any", "founded_year_min": "", "founded_year_max": "",
        "exclude_contacted": True, "exclude_registered": True,
        "exclude_no_email": False, "exclude_duplicates": True,
    }
    m = re.search(r"(?:cré[eé]e?s?|fond[eé]e?s?)\s+(?:depuis|après|apres)\s+(?:l['’]année\s+)?(19\d{2}|20\d{2})", low)
    if not m:
        m = re.search(r"(?:depuis|après|apres)\s+(19\d{2}|20\d{2})", low)
    if m:
        filters["founded_year_min"] = m.group(1)
    m = re.search(r"(?:cré[eé]e?s?|fond[eé]e?s?)\s+(?:avant|jusqu['’]?à|jusqu a)\s+(19\d{2}|20\d{2})", low)
    if not m:
        m = re.search(r"(?:avant|jusqu['’]?à|jusqu a)\s+(19\d{2}|20\d{2})", low)
    if m:
        filters["founded_year_max"] = m.group(1)

    if "avec email" in low or "avec e-mail" in low or "email vérifié" in low or "email verifie" in low:
        filters["has_email"] = "yes"
    if "sans email" in low or "sans e-mail" in low:
        filters["has_email"] = "no"
    if "avec site" in low or "site internet" in low or "site web" in low:
        filters["has_website"] = "yes"
    if "sans site" in low:
        filters["has_website"] = "no"
    if "avec téléphone" in low or "avec telephone" in low:
        filters["has_phone"] = "yes"
    if "sans téléphone" in low or "sans telephone" in low:
        filters["has_phone"] = "no"

    campaign_name = "Mission Aura"
    if industry:
        campaign_name += f" — {industry}"
    if city:
        campaign_name += f" {city}"
    elif canton:
        campaign_name += f" {canton}"

    return {
        "campaign_name": campaign_name[:100],
        "industry": industry,
        "country": "CH",
        "canton": canton or "VD",
        "city": city or "",
        "postal_code": "",
        "radius_km": 20,
        "max_results": max_results,
        "provider": "aura_intelligence",
        "filters": filters,
        "language": "auto",
        "ai_analysis_enabled": True,
    }


async def _llm_parse(text: str, model: str) -> Optional[dict[str, Any]]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None
    client = AsyncOpenAI(api_key=key)
    system = (
        "Tu transformes une mission de prospection B2B en critères de recherche structurés. "
        "Réponds uniquement en JSON. N'invente jamais de ville, canton ou exigence absente. "
        "Le champ industry doit décrire l'activité des entreprises recherchées, pas l'offre vendue."
    )
    prompt = f"""Mission utilisateur:\n{text}\n\nRetourne exactement ce JSON:\n{{
      "industry": "activité recherchée, concise",
      "country": "CH",
      "canton": "code canton suisse ou null",
      "city": "ville ou null",
      "radius_km": 20,
      "max_results": 20,
      "filters": {{
        "has_website": "yes|no|any",
        "has_email": "yes|no|any",
        "has_phone": "yes|no|any",
        "founded_year_min": "année ou chaîne vide",
        "founded_year_max": "année ou chaîne vide"
      }},
      "summary": "une phrase résumant la cible"
    }}"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None


async def parse_mission(text: str, model: str = "gpt-5.4", allow_ai: bool = True) -> dict[str, Any]:
    base = _heuristic_parse(text)
    used_ai = False
    if allow_ai:
        ai = await _llm_parse(text, model)
        if ai:
            used_ai = True
            # Only overwrite with explicit, sane values.
            if ai.get("industry"):
                base["industry"] = str(ai["industry"]).strip()[:80]
            if ai.get("country"):
                base["country"] = str(ai["country"]).upper()[:2]
            if ai.get("canton"):
                base["canton"] = str(ai["canton"]).upper()[:3]
            if ai.get("city"):
                base["city"] = str(ai["city"]).strip()[:80]
            try:
                base["radius_km"] = max(1, min(100, int(ai.get("radius_km") or base["radius_km"])))
                base["max_results"] = max(1, min(50, int(ai.get("max_results") or base["max_results"])))
            except Exception:
                pass
            aif = ai.get("filters") or {}
            for k in ("has_website", "has_email", "has_phone"):
                if aif.get(k) in ("yes", "no", "any"):
                    base["filters"][k] = aif[k]
            for k in ("founded_year_min", "founded_year_max"):
                v = aif.get(k)
                if v not in (None, ""):
                    try:
                        y = int(v)
                        if 1800 <= y <= 2026:
                            base["filters"][k] = str(y)
                    except Exception:
                        pass
            base["mission_summary"] = str(ai.get("summary") or "").strip()[:300]

    if not base.get("industry"):
        # Keep the user in control rather than inventing an industry.
        base["needs_industry_confirmation"] = True
    base["used_ai"] = used_ai
    base["original_mission"] = text
    return base


def build_clone_template(prospect: dict, campaign: Optional[dict] = None) -> dict[str, Any]:
    criteria = (campaign or {}).get("criteria") or {}
    industry = prospect.get("business_domain") or prospect.get("industry") or criteria.get("industry") or ""
    founded = prospect.get("founded_year")
    filters = {
        "has_website": "yes" if prospect.get("website") else "any",
        "has_email": "yes" if prospect.get("email") else "any",
        "has_phone": "yes" if prospect.get("phone") else "any",
        "business_domain": prospect.get("business_domain") or "any",
        "founded_year_min": "",
        "founded_year_max": "",
        "exclude_contacted": True,
        "exclude_registered": True,
        "exclude_no_email": bool(prospect.get("email")),
        "exclude_duplicates": True,
    }
    # A narrow age band is only a suggestion, never a hard fact requirement.
    if isinstance(founded, int):
        filters["founded_year_min"] = str(max(1800, founded - 5))
        filters["founded_year_max"] = str(min(2026, founded + 5))

    city = prospect.get("city") or criteria.get("city") or ""
    canton = prospect.get("canton") or criteria.get("canton") or "VD"
    name = prospect.get("company_name") or "ce client"
    mission = f"Trouver des entreprises similaires à {name}, activité {industry or 'similaire'}"
    if city:
        mission += f" autour de {city}"
    elif canton:
        mission += f" dans le canton {canton}"

    return {
        "source_prospect": {
            "id": prospect.get("id"),
            "company_name": name,
            "business_domain": prospect.get("business_domain"),
            "founded_year": founded,
            "city": city,
            "canton": canton,
        },
        "criteria": {
            "campaign_name": f"Clones de {name}"[:100],
            "industry": industry,
            "country": prospect.get("country") or criteria.get("country") or "CH",
            "canton": canton,
            "city": city,
            "postal_code": "",
            "radius_km": criteria.get("radius_km") or 20,
            "max_results": min(50, max(10, int(criteria.get("max_results") or 20))),
            "provider": "aura_intelligence",
            "filters": filters,
            "language": criteria.get("language") or "auto",
            "ai_analysis_enabled": True,
        },
        "mission": mission,
    }
