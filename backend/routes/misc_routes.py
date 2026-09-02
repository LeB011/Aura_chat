import os
"""Activities, Security, Integrations, Settings, Analytics, Demo routes."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from models import Activity, Prospect, Campaign, AIAnalysis, now_iso, new_id
from auth import get_current_user
from db import get_db
import random

# ---- Activities ----
activities_router = APIRouter(prefix="/activities", tags=["activities"])


@activities_router.get("")
async def list_activities(limit: int = 200, user: dict = Depends(get_current_user)):
    db = get_db()
    return await db.activities.find({"organization_id": user["organization_id"]},
                                      {"_id": 0}).sort("created_at", -1).limit(limit).to_list(None)


# ---- Security ----
security_router = APIRouter(prefix="/security", tags=["security"])


@security_router.get("")
async def get_security(user: dict = Depends(get_current_user)):
    db = get_db()
    s = await db.security_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
    return s


SECURITY_ALLOWED_KEYS = {
    "human_approval_required", "daily_sending_limit", "hourly_sending_limit",
    "delay_between_messages_minutes", "random_delay", "duplicate_protection",
    "existing_customer_exclusion", "dnc_list_enabled", "unsubscribe_protection",
    "invalid_email_protection", "generic_email_warning", "personal_email_warning",
    "require_professional_relevance", "confidence_threshold",
    "ai_hallucination_protection", "sensitive_industry_protection",
    "compliance_review_required", "blacklist",
}


@security_router.patch("")
async def update_security(payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in SECURITY_ALLOWED_KEYS}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    allowed["updated_at"] = now_iso()
    await db.security_settings.update_one(
        {"organization_id": user["organization_id"]},
        {"$set": allowed},
    )
    return await db.security_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})


@security_router.post("/kill-switch")
async def toggle_kill_switch(payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    active = bool(payload.get("active", True))
    await db.security_settings.update_one(
        {"organization_id": user["organization_id"]},
        {"$set": {"kill_switch_active": active, "updated_at": now_iso()}},
    )
    act = Activity(
        organization_id=user["organization_id"], user_id=user["id"],
        action="Kill switch " + ("activé" if active else "désactivé"),
        action_type="security.kill_switch_toggled",
        entity_type="security_settings", entity_id=user["organization_id"],
        status="warning" if active else "info",
    )
    await db.activities.insert_one(act.model_dump())
    return {"kill_switch_active": active}


# ---- Integrations ----
integrations_router = APIRouter(prefix="/integrations", tags=["integrations"])

DEFAULT_INTEGRATIONS = [
    ("openai", "OpenAI", "Bot"),
    ("google_sheets", "Google Sheets", "Sheet"),
    ("gmail", "Gmail", "Mail"),
    ("outlook", "Outlook", "Mail"),
    ("smtp", "SMTP", "Send"),
    ("google_maps", "Google Maps", "Map"),
    ("google_places", "Google Places", "Map"),
    ("tinyfish", "TinyFish Search + Fetch", "Search"),
    ("crm", "CRM", "Database"),
    ("make", "Make", "Workflow"),
    ("zapier", "Zapier", "Zap"),
    ("webhook", "Webhook", "Webhook"),
    ("csv", "CSV Import/Export", "FileSpreadsheet"),
    ("custom_api", "API personnalisée", "Code"),
]


@integrations_router.get("")
async def list_integrations(user: dict = Depends(get_current_user)):
    db = get_db()
    existing = await db.integrations.find({"organization_id": user["organization_id"]},
                                            {"_id": 0}).to_list(None)
    existing_by_key = {i["key"]: i for i in existing}
    result = []
    for key, name, icon in DEFAULT_INTEGRATIONS:
        if key in existing_by_key:
            existing_by_key[key]["icon"] = icon
            existing_by_key[key]["name"] = name
            result.append(existing_by_key[key])
        else:
            result.append({
                "id": new_id(),
                "organization_id": user["organization_id"],
                "key": key,
                "name": name,
                "icon": icon,
                "status": "not_configured",
                "connected": False,
                "config": {},
                "last_error": None,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
    # Include any extra org-specific integrations that are not in defaults
    for k, integ in existing_by_key.items():
        if k not in {d[0] for d in DEFAULT_INTEGRATIONS}:
            result.append(integ)
    # Server-managed integrations reflect REAL environment state.
    for integ in result:
        if integ.get("key") == "google_places":
            configured = bool(os.environ.get("GOOGLE_PLACES_API_KEY"))
            integ["connected"] = configured
            integ["status"] = "connected" if configured else "not_configured"
            integ["managed_server_side"] = True
        elif integ.get("key") == "tinyfish":
            configured = bool(os.environ.get("TINYFISH_API_KEY"))
            integ["connected"] = configured
            integ["status"] = "connected" if configured else "not_configured"
            integ["managed_server_side"] = True
        elif integ.get("key") == "openai":
            configured = bool(os.environ.get("OPENAI_API_KEY"))
            integ["connected"] = configured
            integ["status"] = "connected" if configured else "not_configured"
            integ["managed_server_side"] = True
    return result


@integrations_router.post("/{integration_key}/validate")
async def validate_integration(integration_key: str, user: dict = Depends(get_current_user)):
    if integration_key == "google_places":
        from providers.prospect_provider import get_provider
        provider = get_provider("google_places")
        ok, error = await provider.validate()
        return {"ok": ok, "status": "connected" if ok else ("not_configured" if not os.environ.get("GOOGLE_PLACES_API_KEY") else "error"), "error": error}
    if integration_key == "tinyfish":
        from providers.prospect_provider import get_provider
        provider = get_provider("tinyfish")
        ok, error = await provider.validate()
        return {"ok": ok, "status": "connected" if ok else ("not_configured" if not os.environ.get("TINYFISH_API_KEY") else "error"), "error": error}
    if integration_key == "openai":
        ok = bool(os.environ.get("OPENAI_API_KEY"))
        return {"ok": ok, "status": "connected" if ok else "not_configured", "error": None if ok else "OPENAI_API_KEY manquante"}
    raise HTTPException(400, "Validation automatique non disponible pour cette intégration")


@integrations_router.patch("/{integration_key}")
async def update_integration(integration_key: str, payload: dict, user: dict = Depends(get_current_user)):
    """Update an integration. `connected` is only accepted when `status`='connected'.
    API keys/secrets stay server-side; the response never echoes them back."""
    db = get_db()
    existing = await db.integrations.find_one(
        {"organization_id": user["organization_id"], "key": integration_key}, {"_id": 0}
    )

    # Determine new state carefully — do not fake "connected" without config
    new_status = payload.get("status")
    new_config = payload.get("config")
    connected = payload.get("connected")

    if existing is None:
        doc = {
            "id": new_id(),
            "organization_id": user["organization_id"],
            "key": integration_key,
            "name": integration_key,
            "status": new_status or "not_configured",
            "connected": bool(connected),
            "config": new_config or {},
            "last_error": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        # Guard: cannot be connected without any config
        if doc["connected"] and not doc["config"]:
            doc["connected"] = False
            doc["status"] = "not_configured"
        await db.integrations.insert_one(doc)
    else:
        allowed = {}
        if new_status is not None:
            allowed["status"] = new_status
        if new_config is not None:
            allowed["config"] = new_config
        if connected is not None:
            allowed["connected"] = bool(connected)
        # Enforce integrity: cannot mark as "connected" without a real config
        merged_config = allowed.get("config", existing.get("config", {}))
        if allowed.get("connected") and not merged_config:
            allowed["connected"] = False
            allowed["status"] = "not_configured"
        if not allowed:
            raise HTTPException(400, "Aucun changement")
        allowed["updated_at"] = now_iso()
        await db.integrations.update_one(
            {"id": existing["id"]},
            {"$set": allowed},
        )

    result = await db.integrations.find_one(
        {"organization_id": user["organization_id"], "key": integration_key}, {"_id": 0}
    )
    # Do not echo raw secrets back to the client
    if result and result.get("config"):
        result["config"] = {k: ("***" if k in {"api_key", "secret", "token", "password"} else v)
                             for k, v in result["config"].items()}
    return result


# ---- Settings ----
settings_router = APIRouter(prefix="/settings", tags=["settings"])


@settings_router.get("/ai")
async def get_ai(user: dict = Depends(get_current_user)):
    db = get_db()
    return await db.ai_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})


AI_ALLOWED_KEYS = {
    "provider", "model", "creativity", "language",
    "max_cost_per_operation", "max_daily_usage",
}


@settings_router.patch("/ai")
async def update_ai(payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in AI_ALLOWED_KEYS}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    # Basic validation
    if "creativity" in allowed:
        allowed["creativity"] = max(0.0, min(1.0, float(allowed["creativity"])))
    if "max_cost_per_operation" in allowed:
        allowed["max_cost_per_operation"] = max(0.0, float(allowed["max_cost_per_operation"]))
    if "max_daily_usage" in allowed:
        allowed["max_daily_usage"] = max(0.0, float(allowed["max_daily_usage"]))
    allowed["updated_at"] = now_iso()
    await db.ai_settings.update_one(
        {"organization_id": user["organization_id"]},
        {"$set": allowed},
    )
    return await db.ai_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})


@settings_router.get("/organization")
async def get_org(user: dict = Depends(get_current_user)):
    db = get_db()
    return await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})


@settings_router.patch("/organization")
async def update_org(payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: payload[k] for k in ("name", "country", "test_mode") if k in payload}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    allowed["updated_at"] = now_iso()
    # Audit if test_mode is being switched OFF
    if "test_mode" in allowed and allowed["test_mode"] is False:
        act = Activity(
            organization_id=user["organization_id"], user_id=user["id"],
            action="Test Mode désactivé", action_type="security.test_mode_off",
            status="warning",
        )
        await db.activities.insert_one(act.model_dump())
    await db.organizations.update_one({"id": user["organization_id"]}, {"$set": allowed})
    return await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})


# ---- Analytics ----
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    db = get_db()
    org_q = {"organization_id": user["organization_id"]}
    prospects = await db.prospects.find(org_q, {"_id": 0}).to_list(None)
    messages = await db.messages.find(org_q, {"_id": 0}).to_list(None)
    campaigns = await db.campaigns.find(org_q, {"_id": 0}).to_list(None)
    agents = await db.agents.find(org_q, {"_id": 0}).to_list(None)

    qualified = [p for p in prospects if p.get("qualification_score", (p.get("ai_analysis") or {}).get("ai_opportunity_score", 0)) >= 61]
    replies = [p for p in prospects if p.get("status") == "replied"]
    meetings = [p for p in prospects if p.get("status") == "meeting"]
    sent = [m for m in messages if m.get("status") == "sent"]
    prepared = [m for m in messages if m.get("status") in ("draft", "needs_review", "approved", "test")]

    scores = [p.get("qualification_score", (p.get("ai_analysis") or {}).get("ai_opportunity_score", 0))
                for p in prospects if p.get("qualification_score") or p.get("ai_analysis")]
    avg_score = round(sum(scores) / len(scores)) if scores else 0

    # By city
    by_city = {}
    for p in prospects:
        c = p.get("city") or "N/A"
        by_city[c] = by_city.get(c, 0) + 1
    # By industry
    by_industry = {}
    for p in prospects:
        c = p.get("industry") or "N/A"
        by_industry[c] = by_industry.get(c, 0) + 1
    # By status
    by_status = {}
    for p in prospects:
        by_status[p.get("status", "new")] = by_status.get(p.get("status", "new"), 0) + 1
    # By day (created_at prefix)
    by_day = {}
    for p in prospects:
        day = (p.get("created_at") or "")[:10]
        if day:
            by_day[day] = by_day.get(day, 0) + 1

    conv_rate = round((len(meetings) / len(prospects)) * 100, 1) if prospects else 0

    return {
        "kpis": {
            "active_agents": sum(1 for a in agents if a.get("enabled")),
            "prospects_found": len(prospects),
            "qualified": len(qualified),
            "messages_prepared": len(prepared),
            "messages_sent": len(sent),
            "replies": len(replies),
            "meetings": len(meetings),
            "response_rate": round((len(replies) / max(1, len(sent))) * 100, 1),
            "avg_score": avg_score,
            "campaigns": len(campaigns),
        },
        "by_city": [{"name": k, "value": v} for k, v in sorted(by_city.items(), key=lambda x: -x[1])[:8]],
        "by_industry": [{"name": k, "value": v} for k, v in sorted(by_industry.items(), key=lambda x: -x[1])[:8]],
        "by_status": [{"name": k, "value": v} for k, v in by_status.items()],
        "by_day": [{"name": k, "value": v} for k, v in sorted(by_day.items())][-14:],
    }


# ---- Demo data ----
demo_router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_PROSPECTS = [
    ("Electricité Martin SA", "Electricien", "Lausanne", "1004", "VD", 87, "to_contact", "info@electricite-martin.ch", "+41 21 555 12 34"),
    ("Garage du Léman", "Garage", "Morges", "1110", "VD", 72, "analyzed", "contact@garage-leman.ch", "+41 21 555 44 22"),
    ("ABC Peinture", "Peintre", "Renens", "1020", "VD", 44, "new", None, "+41 21 555 91 20"),
    ("Fiduciaire Léman & Associés", "Fiduciaire", "Nyon", "1260", "VD", 81, "to_contact", "info@fid-leman.ch", "+41 22 555 88 40"),
    ("Salon Coup de Style", "Coiffeur", "Vevey", "1800", "VD", 55, "analyzed", None, "+41 21 555 23 45"),
    ("PlombServices Sàrl", "Plombier", "Yverdon", "1400", "VD", 68, "analyzed", "info@plombservices.ch", "+41 24 555 77 88"),
    ("Immo Alpes SA", "Agence immobilière", "Sion", "1950", "VS", 78, "to_contact", "contact@immo-alpes.ch", "+41 27 555 33 22"),
    ("Ristorante Bellini", "Restaurant", "Lugano", "6900", "TI", 63, "analyzed", "reservation@bellini.ch", "+41 91 555 66 77"),
]


@demo_router.post("/seed")
async def seed_demo(user: dict = Depends(get_current_user)):
    db = get_db()
    # Remove any existing demo data first
    await db.prospects.delete_many({"organization_id": user["organization_id"], "is_demo": True})
    await db.campaigns.delete_many({"organization_id": user["organization_id"], "name": {"$regex": "^Démo"}})

    from models import SearchCriteria as SC
    criteria = SC(campaign_name="Démo Suisse Romande", industry="PME multi-secteurs",
                   country="CH", canton="VD", city="Lausanne", radius_km=50, max_results=8,
                   ai_analysis_enabled=True)
    camp = Campaign(organization_id=user["organization_id"], user_id=user["id"],
                     name=criteria.campaign_name, criteria=criteria)
    await db.campaigns.insert_one(camp.model_dump())

    inserted = 0
    for company, industry, city, zip_c, canton, score, status, email, phone in DEMO_PROSPECTS:
        analysis = AIAnalysis(
            summary=f"{company} est un acteur {industry.lower()} établi à {city}.",
            main_activity=industry,
            services=[f"{industry} général", "Interventions", "Devis"],
            likely_customers="Particuliers et PME locales",
            digital_maturity="moyenne" if score > 60 else "faible",
            opportunities=["Automatisation des devis", "Réponses clients"] if score > 50 else ["Site à créer"],
            problems=["Réponses clients lentes"],
            ai_use_cases=["Réponses automatiques", "Qualification leads"],
            sales_arguments=[f"Gain de temps mesurable pour {company}"],
            relevance_note="Analyse démonstration.",
            ai_opportunity_score=score,
            confidence_score=max(45, score - 12),
            is_hypothesis=True,
        )
        p = Prospect(
            organization_id=user["organization_id"],
            campaign_id=camp.id,
            company_name=company, industry=industry, city=city, postal_code=zip_c, canton=canton,
            country="CH", email=email, phone=phone,
            website=f"https://www.{company.lower().split()[0]}.ch" if score > 50 else None,
            description=f"{industry} à {city}.",
            source="demo", source_provider="demo", status=status, ai_analysis=analysis, is_demo=True,
            qualification_score=score,
            qualification_status=("excellent" if score >= 80 else "good" if score >= 60
                                    else "medium" if score >= 40 else "low"),
            qualification_confidence=max(45, score - 12),
            qualification_reasons=[
                {"delta": 15, "label": "Secteur cible identifié", "evidence": industry},
                {"delta": 10, "label": "Localisation vérifiée", "evidence": f"{city}, {canton}"},
                {"delta": 15 if score > 50 else -5, "label": "Site internet" if score > 50 else "Aucun site",
                 "evidence": "Site présent" if score > 50 else "Aucune présence en ligne"},
                {"delta": 10 if email else -10, "label": "Email professionnel" if email else "Aucun email",
                 "evidence": email or "N/A"},
            ],
            verified_fields=[f for f in ("company_name", "industry", "city", "canton", "country") if True]
                             + ([f for f in ("website", "email", "phone") if score > 50 and (score > 60 or email)]),
            unverified_fields=["decision_maker", "employee_count", "revenue"],
        )
        await db.prospects.insert_one(p.model_dump())
        inserted += 1

    await db.campaigns.update_one({"id": camp.id}, {"$set": {"stats.prospects_found": inserted,
                                                                "stats.qualified": sum(1 for x in DEMO_PROSPECTS if x[5] >= 61),
                                                                "stats.to_contact": sum(1 for x in DEMO_PROSPECTS if x[6] == "to_contact")}})

    # Add a couple of activity logs
    demos = [
        ("Prospect AI a trouvé 8 entreprises", "Démo Suisse Romande", "info"),
        ("Analyse IA terminée", "Démo Suisse Romande", "success"),
        ("3 messages ont été préparés", "Démo Suisse Romande", "info"),
    ]
    for action, target, status in demos:
        act = Activity(organization_id=user["organization_id"], action=action, target=target, status=status)
        await db.activities.insert_one(act.model_dump())

    return {"ok": True, "prospects": inserted, "campaign_id": camp.id}


@demo_router.delete("/clear")
async def clear_demo(user: dict = Depends(get_current_user)):
    db = get_db()
    r1 = await db.prospects.delete_many({"organization_id": user["organization_id"], "is_demo": True})
    r2 = await db.campaigns.delete_many({"organization_id": user["organization_id"], "name": {"$regex": "^Démo"}})
    return {"ok": True, "prospects_deleted": r1.deleted_count, "campaigns_deleted": r2.deleted_count}
