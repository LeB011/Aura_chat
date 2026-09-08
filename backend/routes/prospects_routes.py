"""Prospect + Campaign + Search routes (V2)."""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from typing import Optional
import csv
import io
import os
from models import (SearchCriteria, Campaign, Prospect, ProspectUpdate,
                    Activity, now_iso)
from auth import get_current_user, require_agent_access
from db import get_db
from providers.prospect_provider import get_provider, list_providers
from services.ai_service import analyze_prospect, compute_qualification
from services.opportunity_service import build_opportunity
from services.mission_service import parse_mission, build_clone_template
from services import quotas
from services.rate_limit import rate_limit_campaign

router = APIRouter(tags=["prospects"])


async def _log(db, org_id: str, user_id: str, action: str, action_type: str,
                entity_type: str = None, entity_id: str = None, target: str = None,
                result: str = None, status: str = "info", meta: dict = None):
    act = Activity(organization_id=org_id, user_id=user_id, action=action,
                    action_type=action_type, entity_type=entity_type,
                    entity_id=entity_id, target=target, result=result,
                    status=status, meta=meta or {})
    await db.activities.insert_one(act.model_dump())


@router.get("/prospect-sources")
async def sources(user: dict = Depends(get_current_user)):
    db = get_db()
    integrations = await db.integrations.find(
        {"organization_id": user["organization_id"]}, {"_id": 0}
    ).to_list(None)
    integrations_by_key = {i["key"]: i for i in integrations}
    providers = list_providers()
    for p in providers:
        integ = integrations_by_key.get(p["key"])
        # Ask the provider whether it is configured for this org
        provider_impl = get_provider(p["key"])
        p["is_configured"] = provider_impl.is_configured(integ) if hasattr(provider_impl, "is_configured") else True
    return providers


# ---------- Phase 1 Commercial: Mission Mode / Clone ----------
@router.post("/prospect-ai/mission/parse")
async def parse_prospect_mission(payload: dict, user: dict = Depends(require_agent_access("prospect_ai"))):
    text = str(payload.get("text") or "").strip()
    if len(text) < 8:
        raise HTTPException(400, "Décrivez la mission en quelques mots.")
    if len(text) > 1500:
        raise HTTPException(400, "Mission trop longue (1500 caractères maximum).")
    db = get_db()
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})
    settings = await db.ai_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
    model = (settings or {}).get("model", "gpt-5.4")
    allow_ai = bool(payload.get("use_ai", True) and os.environ.get("OPENAI_API_KEY"))
    if allow_ai:
        await quotas.check_and_record_ai(org)
    result = await parse_mission(text, model=model, allow_ai=allow_ai)
    await _log(db, user["organization_id"], user["id"],
               "Mission Prospect AI interprétée", "prospect.mission_parsed",
               status="success", meta={"used_ai": result.get("used_ai", False), "industry": result.get("industry")})
    return result


@router.post("/prospects/{prospect_id}/clone-profile")
async def clone_prospect_profile(prospect_id: str, user: dict = Depends(require_agent_access("prospect_ai"))):
    db = get_db()
    prospect = await db.prospects.find_one({"id": prospect_id, "organization_id": user["organization_id"]}, {"_id": 0})
    if not prospect:
        raise HTTPException(404, "Prospect introuvable")
    campaign = None
    if prospect.get("campaign_id"):
        campaign = await db.campaigns.find_one({"id": prospect.get("campaign_id"), "organization_id": user["organization_id"]}, {"_id": 0})
    template = build_clone_template(prospect, campaign)
    await _log(db, user["organization_id"], user["id"],
               "Profil similaire préparé", "prospect.clone_profile",
               entity_type="prospect", entity_id=prospect_id, target=prospect.get("company_name"), status="success")
    return template


# ---------- Campaigns ----------
@router.post("/campaigns")
async def create_campaign(criteria: SearchCriteria, request: Request,
                            user: dict = Depends(require_agent_access("prospect_ai"))):
    db = get_db()
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})
    test_mode = bool(org.get("test_mode", True)) if org else True

    # Phase 0B: rate limit + quota enforcement
    rate_limit_campaign(request, user["organization_id"])
    await quotas.check_provider_search(org)

    # V2.1: honour requested provider. Test Mode NO LONGER forces mock —
    # read-only searches are allowed. Only outbound sending is blocked elsewhere.
    provider_key = (criteria.provider or "mock").strip()
    provider = get_provider(provider_key)
    if provider is None:
        raise HTTPException(400, f"Provider inconnu: {provider_key}")

    # Server-side limits
    limits = (org or {}).get("usage_limits") or {}
    max_allowed = int(limits.get("max_results_per_search", 50))
    if criteria.max_results > max_allowed:
        criteria.max_results = max_allowed

    # Phase 0B: graceful provider fallback. If the user explicitly picked
    # google_places or tinyfish and it's not configured, silently upgrade to
    # aura_intelligence when at least one of the two backing keys is present.
    if provider_key in ("google_places", "tinyfish"):
        integ = await db.integrations.find_one(
            {"organization_id": user["organization_id"], "key": provider_key}, {"_id": 0}
        )
        if not provider.is_configured(integ):
            aura = get_provider("aura_intelligence")
            if aura and aura.is_configured(None):
                await _log(db, user["organization_id"], user["id"],
                            f"Fallback vers Aura Intelligence ({provider_key} indisponible)",
                            "provider.fallback",
                            meta={"from": provider_key, "to": "aura_intelligence"},
                            status="info")
                provider_key = "aura_intelligence"
                provider = aura

    # Check configuration for real providers (after fallback)
    if provider_key != "mock":
        integ = await db.integrations.find_one(
            {"organization_id": user["organization_id"], "key": provider_key}, {"_id": 0}
        )
        if not provider.is_configured(integ):
            raise HTTPException(
                400,
                f"Le provider '{provider.label}' n'est pas encore configuré. "
                "Ajoutez les clés API côté serveur (TINYFISH_API_KEY et/ou "
                "GOOGLE_PLACES_API_KEY) ou choisissez le provider Mock."
            )

    campaign = Campaign(
        organization_id=user["organization_id"],
        user_id=user["id"],
        name=criteria.campaign_name,
        criteria=criteria,
        provider_used=provider_key,
        offer=criteria.offer,
    )
    await db.campaigns.insert_one(campaign.model_dump())
    await _log(db, user["organization_id"], user["id"],
                "Campagne créée", "campaign.created",
                entity_type="campaign", entity_id=campaign.id,
                target=campaign.name, status="success",
                meta={"provider": provider_key})

    # Run provider search
    try:
        raw = await provider.search(criteria)
    except Exception as e:
        await _log(db, user["organization_id"], user["id"],
                    "Erreur provider", "provider.search_failed",
                    entity_type="campaign", entity_id=campaign.id,
                    target=campaign.name, result=str(e), status="error",
                    meta={"provider": provider_key})
        raise HTTPException(400, f"Erreur du provider: {e}")

    await _log(db, user["organization_id"], user["id"],
                f"{provider.label}: {len(raw)} entreprises trouvées",
                "provider.search_completed",
                entity_type="campaign", entity_id=campaign.id,
                target=campaign.name, result=str(len(raw)), status="info",
                meta={"provider": provider_key, "test_mode": test_mode})

    prospects_saved = []
    dedup_skipped = 0
    ai_settings = await db.ai_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
    model = (ai_settings or {}).get("model", "gpt-5.4")

    # Phase 0B: check monthly prospect quota BEFORE inserting any (use raw count as upper bound)
    await quotas.check_prospects_add(org, len(raw))
    # Also record the provider search (once per campaign, regardless of result count)
    await quotas.record_provider_search(org)

    for item in raw:
        # ---- Deduplication (V2.1) ----
        dup_query = {"organization_id": user["organization_id"]}
        or_clauses = []
        if item.get("external_id"):
            or_clauses.append({"external_id": item["external_id"]})
        if item.get("website"):
            or_clauses.append({"website": item["website"]})
        if item.get("phone"):
            or_clauses.append({"phone": item["phone"]})
        if not or_clauses:
            or_clauses.append({"company_name": item.get("company_name"), "city": item.get("city")})
        dup_query["$or"] = or_clauses
        existing = await db.prospects.find_one(dup_query, {"_id": 0})
        if existing:
            # attach to new campaign but do NOT duplicate
            await db.prospects.update_one(
                {"id": existing["id"]},
                {"$set": {"campaign_id": campaign.id, "updated_at": now_iso()}},
            )
            dedup_skipped += 1
            continue

        p = Prospect(organization_id=user["organization_id"], campaign_id=campaign.id,
                       retrieved_at=now_iso(), **item)

        # Explainable qualification
        qual = compute_qualification(p.model_dump(), criteria.service_to_sell,
                                       min_score=criteria.min_score)
        p.qualification_score = qual["qualification_score"]
        p.qualification_status = qual["qualification_status"]
        p.qualification_confidence = qual["qualification_confidence"]
        p.qualification_reasons = qual["qualification_reasons"]
        p.verified_fields = qual["verified_fields"]
        p.unverified_fields = qual["unverified_fields"]

        if criteria.ai_analysis_enabled:
            # Test Mode blocks outbound actions, not read-only AI analysis.
            analysis = await analyze_prospect(p.model_dump(), criteria.service_to_sell,
                                                test_mode=False, model=model)
            analysis["ai_opportunity_score"] = p.qualification_score
            p.ai_analysis = analysis

        # V8: explainable commercial opportunity score (no invented facts).
        opp = build_opportunity(p.model_dump(), criteria.service_to_sell, criteria.offer or {}, criteria.model_dump())
        p.opportunity = opp
        p.fit_score = opp["fit_score"]
        p.need_score = opp["need_score"]
        p.data_quality_score = opp["data_quality_score"]
        p.contactability_score = opp["contactability_score"]
        p.commercial_score = opp["commercial_score"]
        p.aura_grade = opp["aura_grade"]
        p.why_this_prospect = opp["why_this_prospect"]
        p.verified_observations = opp["verified_observations"]
        p.last_verified_at = now_iso()

        if p.qualification_score >= 61:
            p.status = "to_contact"
        elif p.qualification_score >= 30:
            p.status = "analyzed"
        else:
            p.status = "new"

        await db.prospects.insert_one(p.model_dump())
        prospects_saved.append(p.model_dump())

    if dedup_skipped:
        await _log(db, user["organization_id"], user["id"],
                    f"Dédoublonnage : {dedup_skipped} doublons évités",
                    "prospect.dedup", entity_type="campaign", entity_id=campaign.id,
                    status="info", meta={"skipped": dedup_skipped})

    qualified = sum(1 for p in prospects_saved if p.get("qualification_score", 0) >= 61)
    to_contact = sum(1 for p in prospects_saved if p["status"] == "to_contact")

    # Phase 0B: increment monthly prospect counter with actual inserted count
    if prospects_saved:
        await quotas.record_prospects_added(org, len(prospects_saved))

    await db.campaigns.update_one(
        {"id": campaign.id},
        {"$set": {
            "stats.prospects_found": len(prospects_saved),
            "stats.qualified": qualified,
            "stats.to_contact": to_contact,
        }},
    )
    if criteria.ai_analysis_enabled and prospects_saved:
        await _log(db, user["organization_id"], user["id"],
                    "Qualification IA terminée", "prospect.qualified_batch",
                    entity_type="campaign", entity_id=campaign.id,
                    target=campaign.name, result=f"{qualified} qualifiés", status="success")

    await db.agents.update_one(
        {"organization_id": user["organization_id"], "key": "prospect_ai"},
        {"$set": {"last_activity_at": now_iso()}},
    )

    campaign_out = await db.campaigns.find_one({"id": campaign.id}, {"_id": 0})
    return {"campaign": campaign_out, "prospects_count": len(prospects_saved),
            "duplicates_skipped": dedup_skipped}


@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(get_current_user)):
    db = get_db()
    return await db.campaigns.find({"organization_id": user["organization_id"]},
                                     {"_id": 0}).sort("created_at", -1).to_list(None)


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    c = await db.campaigns.find_one({"id": campaign_id, "organization_id": user["organization_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Campagne introuvable")
    return c


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: payload[k] for k in ("status", "mode", "name", "offer") if k in payload}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    allowed["updated_at"] = now_iso()
    await db.campaigns.update_one(
        {"id": campaign_id, "organization_id": user["organization_id"]},
        {"$set": allowed},
    )
    return await db.campaigns.find_one({"id": campaign_id, "organization_id": user["organization_id"]}, {"_id": 0})


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await db.campaigns.delete_one({"id": campaign_id, "organization_id": user["organization_id"]})
    await db.prospects.delete_many({"campaign_id": campaign_id, "organization_id": user["organization_id"]})
    return {"ok": True}


# ---------- CSV import (V2) ----------
@router.post("/prospects/import-csv")
async def import_csv(file: UploadFile = File(...), campaign_id: Optional[str] = None,
                      user: dict = Depends(get_current_user)):
    """Import prospects from a CSV file. Expected headers: company_name (required),
    industry, website, email, phone, address, postal_code, city, canton, country.
    Multi-tenant safe: prospects always attached to the caller's organization."""
    if not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(400, "Fichier CSV requis (.csv)")
    data = await file.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "company_name" not in [f.strip().lower() for f in (reader.fieldnames or [])]:
        raise HTTPException(400, "Le CSV doit contenir au minimum une colonne 'company_name'.")

    db = get_db()
    inserted = 0
    errors = 0
    for row in reader:
        try:
            clean = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            if not clean.get("company_name"):
                errors += 1
                continue
            p = Prospect(
                organization_id=user["organization_id"],
                campaign_id=campaign_id,
                company_name=clean["company_name"],
                industry=clean.get("industry") or None,
                website=clean.get("website") or None,
                email=clean.get("email") or None,
                phone=clean.get("phone") or None,
                address=clean.get("address") or None,
                postal_code=clean.get("postal_code") or None,
                city=clean.get("city") or None,
                canton=clean.get("canton") or None,
                country=clean.get("country") or "CH",
                source="csv",
                source_provider="csv",
                source_url=None,
            )
            qual = compute_qualification(p.model_dump(), [])
            p.qualification_score = qual["qualification_score"]
            p.qualification_status = qual["qualification_status"]
            p.qualification_confidence = qual["qualification_confidence"]
            p.qualification_reasons = qual["qualification_reasons"]
            p.verified_fields = qual["verified_fields"]
            p.unverified_fields = qual["unverified_fields"]
            await db.prospects.insert_one(p.model_dump())
            inserted += 1
        except Exception:
            errors += 1

    await _log(db, user["organization_id"], user["id"],
                "Import CSV effectué", "prospect.csv_imported",
                target=file.filename, result=f"{inserted} importés, {errors} ignorés",
                status="success" if inserted else "warning")
    return {"ok": True, "inserted": inserted, "errors": errors}


# ---------- Prospects ----------
@router.get("/prospects")
async def list_prospects(
    user: dict = Depends(get_current_user),
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    min_score: Optional[int] = None,
    qualification_status: Optional[str] = None,
    business_domain: Optional[str] = None,
    founded_year_min: Optional[int] = None,
    founded_year_max: Optional[int] = None,
    min_commercial_score: Optional[int] = None,
    aura_grade: Optional[str] = None,
    min_verification: Optional[int] = None,
    limit: int = Query(500, le=1000),
):
    db = get_db()
    query = {"organization_id": user["organization_id"]}
    if campaign_id:
        query["campaign_id"] = campaign_id
    if status:
        query["status"] = status
    if qualification_status:
        query["qualification_status"] = qualification_status
    if business_domain:
        query["business_domain"] = business_domain
    if founded_year_min is not None or founded_year_max is not None:
        yr = {}
        if founded_year_min is not None:
            yr["$gte"] = founded_year_min
        if founded_year_max is not None:
            yr["$lte"] = founded_year_max
        query["founded_year"] = yr
    if q:
        query["$or"] = [
            {"company_name": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
            {"industry": {"$regex": q, "$options": "i"}},
        ]
    if min_score is not None:
        query["qualification_score"] = {"$gte": min_score}
    if min_commercial_score is not None:
        query["commercial_score"] = {"$gte": min_commercial_score}
    if aura_grade:
        query["aura_grade"] = aura_grade
    if min_verification is not None:
        query["verification_score"] = {"$gte": min_verification}
    return await db.prospects.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(None)


@router.post("/prospects/{prospect_id}/reverify")
async def reverify_prospect(prospect_id: str, user: dict = Depends(require_agent_access("prospect_ai"))):
    """Re-check an old prospect with Aura Intelligence and recalculate V8 scores."""
    db=get_db()
    p=await db.prospects.find_one({"id":prospect_id,"organization_id":user["organization_id"]},{"_id":0})
    if not p:
        raise HTTPException(404,"Prospect introuvable")
    provider=get_provider("aura_intelligence")
    if not provider or not provider.is_configured():
        raise HTTPException(400,"Aura Intelligence n'est pas configuré (TinyFish et/ou Google Places requis).")
    criteria=SearchCriteria(
        campaign_name=f"Reverify {p.get('company_name')}",
        industry=p.get("business_domain") or p.get("industry") or p.get("company_name"),
        country=p.get("country") or "CH", canton=p.get("canton"), city=p.get("city"),
        postal_code=p.get("postal_code"), max_results=12, provider="aura_intelligence",
        ai_analysis_enabled=False,
    )
    rows=await provider.search(criteria)
    def domain(url):
        from urllib.parse import urlparse
        try:return urlparse(url or "").netloc.lower().removeprefix("www.")
        except Exception:return ""
    pd=domain(p.get("website"))
    pn="".join(ch for ch in (p.get("company_name") or "").lower() if ch.isalnum())
    best=None
    for r in rows:
        rd=domain(r.get("website")); rn="".join(ch for ch in (r.get("company_name") or "").lower() if ch.isalnum())
        if (pd and rd and pd==rd) or (pn and rn and (pn==rn or (len(pn)>5 and (pn in rn or rn in pn)))):
            best=r; break
    if not best:
        raise HTTPException(404,"Aucune correspondance suffisamment fiable trouvée. Le prospect n'a pas été modifié.")
    allowed=("company_name","industry","business_domain","founded_year","founded_year_source","founded_year_confidence",
             "verification_score","verification_level","evidence_sources","evidence","source_confidence","verification",
             "description","website","email","phone","address","postal_code","city","canton","country","source_url",
             "external_id","source_provider","data_type")
    updates={k:best.get(k) for k in allowed if best.get(k) is not None}
    merged={**p,**updates}
    campaign=await db.campaigns.find_one({"id":p.get("campaign_id")},{"_id":0}) if p.get("campaign_id") else None
    services=(campaign or {}).get("criteria",{}).get("service_to_sell") or []
    offer=(campaign or {}).get("offer") or (campaign or {}).get("criteria",{}).get("offer") or {}
    opp=build_opportunity(merged,services,offer,(campaign or {}).get("criteria") or criteria.model_dump())
    updates.update({"opportunity":opp,"fit_score":opp["fit_score"],"need_score":opp["need_score"],
                    "data_quality_score":opp["data_quality_score"],"contactability_score":opp["contactability_score"],
                    "commercial_score":opp["commercial_score"],"aura_grade":opp["aura_grade"],
                    "why_this_prospect":opp["why_this_prospect"],"verified_observations":opp["verified_observations"],
                    "last_verified_at":now_iso(),"updated_at":now_iso()})
    await db.prospects.update_one({"id":prospect_id,"organization_id":user["organization_id"]},{"$set":updates})
    await _log(db,user["organization_id"],user["id"],"Prospect revérifié","prospect.reverified",entity_type="prospect",entity_id=prospect_id,target=updates.get("company_name") or p.get("company_name"),status="success")
    return await db.prospects.find_one({"id":prospect_id},{"_id":0})


@router.post("/prospects/reverify-batch")
async def reverify_batch(payload: dict, user: dict = Depends(require_agent_access("prospect_ai"))):
    ids=(payload or {}).get("prospect_ids") or []
    ids=ids[:25]
    results=[]
    for pid in ids:
        try:
            row=await reverify_prospect(pid,user)
            results.append({"id":pid,"ok":True,"verification_score":row.get("verification_score")})
        except HTTPException as e:
            results.append({"id":pid,"ok":False,"error":str(e.detail)})
        except Exception as e:
            results.append({"id":pid,"ok":False,"error":str(e)[:160]})
    return {"ok":True,"results":results}


@router.get("/prospects/{prospect_id}")
async def get_prospect(prospect_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    p = await db.prospects.find_one({"id": prospect_id, "organization_id": user["organization_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    return p


@router.patch("/prospects/{prospect_id}")
async def update_prospect(prospect_id: str, payload: ProspectUpdate,
                           user: dict = Depends(get_current_user)):
    db = get_db()
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(400, "Aucun changement")
    updates["updated_at"] = now_iso()
    result = await db.prospects.update_one(
        {"id": prospect_id, "organization_id": user["organization_id"]},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Prospect introuvable")
    return await db.prospects.find_one({"id": prospect_id, "organization_id": user["organization_id"]}, {"_id": 0})


@router.post("/prospects/{prospect_id}/notes")
async def add_note(prospect_id: str, payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    note = {"id": __import__("uuid").uuid4().hex, "text": payload.get("text", ""),
            "author": user["full_name"], "at": now_iso()}
    await db.prospects.update_one(
        {"id": prospect_id, "organization_id": user["organization_id"]},
        {"$push": {"notes": note}, "$set": {"updated_at": now_iso()}},
    )
    return note


@router.delete("/prospects/{prospect_id}")
async def delete_prospect(prospect_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await db.prospects.delete_one({"id": prospect_id, "organization_id": user["organization_id"]})
    return {"ok": True}


@router.post("/prospects/bulk")
async def bulk_action(payload: dict, user: dict = Depends(get_current_user)):
    """payload: {action: 'delete'|'set_status'|'archive'|'dnc', ids: [...], status?: str}"""
    db = get_db()
    ids = payload.get("ids", [])
    action = payload.get("action")
    if not ids or not action:
        raise HTTPException(400, "Paramètres manquants")
    q = {"id": {"$in": ids}, "organization_id": user["organization_id"]}
    if action == "delete":
        result = await db.prospects.delete_many(q)
        return {"ok": True, "count": result.deleted_count}
    if action == "set_status":
        new_status = payload.get("status", "new")
        result = await db.prospects.update_many(q, {"$set": {"status": new_status, "updated_at": now_iso()}})
        return {"ok": True, "count": result.modified_count}
    if action == "archive":
        result = await db.prospects.update_many(q, {"$set": {"status": "refused", "updated_at": now_iso()}})
        return {"ok": True, "count": result.modified_count}
    if action == "dnc":
        result = await db.prospects.update_many(q, {"$set": {
            "do_not_contact": True, "status": "do_not_contact", "updated_at": now_iso()
        }})
        return {"ok": True, "count": result.modified_count}
    raise HTTPException(400, "Action inconnue")
