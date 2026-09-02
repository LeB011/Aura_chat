"""Super Admin routes — platform-wide management. Strictly protected."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from models import PlatformSettings, Activity, now_iso
from auth import get_superadmin
from db import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_superadmin)])


async def _log_platform(db, user_id: str, action: str, action_type: str,
                         entity_type: str = None, entity_id: str = None,
                         target: str = None, result: str = None, status: str = "info",
                         meta: dict = None):
    act = Activity(organization_id=None, user_id=user_id, action=action,
                    action_type=action_type, entity_type=entity_type,
                    entity_id=entity_id, target=target, result=result, status=status,
                    meta=meta or {})
    await db.activities.insert_one(act.model_dump())


# ---------- Overview ----------
@router.get("/overview")
async def overview(user: dict = Depends(get_superadmin)):
    db = get_db()
    total_orgs = await db.organizations.count_documents({})
    active_orgs = await db.organizations.count_documents({"suspended": {"$ne": True}})
    suspended_orgs = await db.organizations.count_documents({"suspended": True})
    total_users = await db.users.count_documents({})
    total_prospects = await db.prospects.count_documents({})
    prospects_today = await db.prospects.count_documents(
        {"created_at": {"$gte": now_iso()[:10]}}
    )
    total_campaigns = await db.campaigns.count_documents({})
    active_agents = await db.agents.count_documents({"enabled": True})
    messages_prepared = await db.messages.count_documents({"status": {"$in": ["draft", "needs_review", "approved"]}})
    messages_sent = await db.messages.count_documents({"status": "sent"})
    errors_recent = await db.activities.count_documents(
        {"status": "error", "created_at": {"$gte": now_iso()[:10]}}
    )
    recent_activity = await db.activities.find({}, {"_id": 0}).sort("created_at", -1).limit(15).to_list(None)

    return {
        "total_organizations": total_orgs,
        "active_organizations": active_orgs,
        "suspended_organizations": suspended_orgs,
        "total_users": total_users,
        "total_prospects": total_prospects,
        "prospects_today": prospects_today,
        "total_campaigns": total_campaigns,
        "active_agents": active_agents,
        "messages_prepared": messages_prepared,
        "messages_sent": messages_sent,
        "errors_recent": errors_recent,
        "ai_operations_estimated": messages_prepared + total_prospects,  # V2 stub
        "ai_cost_estimated": 0.0,  # V2: real tracking requires token metering
        "recent_activity": recent_activity,
    }


# ---------- Organizations ----------
@router.get("/organizations")
async def list_organizations(user: dict = Depends(get_superadmin)):
    db = get_db()
    orgs = await db.organizations.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    result = []
    for o in orgs:
        users_count = await db.users.count_documents({"organization_id": o["id"]})
        prospects_count = await db.prospects.count_documents({"organization_id": o["id"]})
        campaigns_count = await db.campaigns.count_documents({"organization_id": o["id"]})
        owner = await db.users.find_one({"organization_id": o["id"], "role": "owner"}, {"_id": 0, "email": 1, "full_name": 1})
        last_activity = await db.activities.find({"organization_id": o["id"]}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(None)
        o["users_count"] = users_count
        o["prospects_count"] = prospects_count
        o["campaigns_count"] = campaigns_count
        o["owner"] = owner
        o["last_activity_at"] = last_activity[0]["created_at"] if last_activity else None
        result.append(o)
    return result


@router.get("/organizations/{org_id}")
async def get_organization(org_id: str, user: dict = Depends(get_superadmin)):
    db = get_db()
    o = await db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Organisation introuvable")
    o["users"] = await db.users.find({"organization_id": org_id}, {"_id": 0, "password_hash": 0}).to_list(None)
    o["campaigns_count"] = await db.campaigns.count_documents({"organization_id": org_id})
    o["prospects_count"] = await db.prospects.count_documents({"organization_id": org_id})
    return o


ORG_ALLOWED_KEYS = {"name", "plan", "plan_status", "country", "usage_limits"}


@router.patch("/organizations/{org_id}")
async def update_organization(org_id: str, payload: dict, user: dict = Depends(get_superadmin)):
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in ORG_ALLOWED_KEYS}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    allowed["updated_at"] = now_iso()
    result = await db.organizations.update_one({"id": org_id}, {"$set": allowed})
    if result.matched_count == 0:
        raise HTTPException(404, "Organisation introuvable")
    await _log_platform(db, user["id"], "Organisation modifiée",
                          "platform.org_updated", entity_type="organization",
                          entity_id=org_id, target=allowed.get("name"), status="info")
    return await db.organizations.find_one({"id": org_id}, {"_id": 0})


@router.post("/organizations/{org_id}/suspend")
async def suspend_organization(org_id: str, payload: dict = None, user: dict = Depends(get_superadmin)):
    db = get_db()
    result = await db.organizations.update_one(
        {"id": org_id},
        {"$set": {"suspended": True, "plan_status": "suspended", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Organisation introuvable")
    await _log_platform(db, user["id"], "Organisation suspendue",
                          "platform.org_suspended", entity_type="organization",
                          entity_id=org_id, status="warning")
    return {"ok": True}


@router.post("/organizations/{org_id}/reactivate")
async def reactivate_organization(org_id: str, user: dict = Depends(get_superadmin)):
    db = get_db()
    result = await db.organizations.update_one(
        {"id": org_id},
        {"$set": {"suspended": False, "plan_status": "active", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Organisation introuvable")
    await _log_platform(db, user["id"], "Organisation réactivée",
                          "platform.org_reactivated", entity_type="organization",
                          entity_id=org_id, status="success")
    return {"ok": True}


# ---------- Users ----------
@router.get("/users")
async def list_users(q: Optional[str] = None, user: dict = Depends(get_superadmin)):
    db = get_db()
    query = {}
    if q:
        query["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
        ]
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(500).to_list(None)
    return users


USER_ALLOWED_KEYS = {"role", "suspended", "full_name"}
ROLE_VALUES = {"member", "admin", "owner", "superadmin"}


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: dict, user: dict = Depends(get_superadmin)):
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in USER_ALLOWED_KEYS}
    if "role" in allowed and allowed["role"] not in ROLE_VALUES:
        raise HTTPException(400, "Rôle invalide")
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    # Safety: cannot suspend or demote yourself (avoids locking the platform)
    if user_id == user["id"]:
        if allowed.get("suspended") is True:
            raise HTTPException(400, "Vous ne pouvez pas suspendre votre propre compte")
        if "role" in allowed and allowed["role"] != "superadmin":
            raise HTTPException(400, "Vous ne pouvez pas retirer votre propre statut superadmin")
    allowed["updated_at"] = now_iso()
    result = await db.users.update_one({"id": user_id}, {"$set": allowed})
    if result.matched_count == 0:
        raise HTTPException(404, "Utilisateur introuvable")
    await _log_platform(db, user["id"], "Utilisateur modifié",
                          "platform.user_updated", entity_type="user",
                          entity_id=user_id, meta={"fields": list(allowed.keys())},
                          status="info")
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


# ---------- Agents catalog (platform-level) ----------
@router.get("/agents")
async def list_agent_catalog(user: dict = Depends(get_superadmin)):
    """Aggregate agent info across all organizations."""
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": "$key",
            "name": {"$first": "$name"},
            "description": {"$first": "$description"},
            "icon": {"$first": "$icon"},
            "status": {"$first": "$status"},
            "installations": {"$sum": 1},
            "enabled_count": {"$sum": {"$cond": [{"$eq": ["$enabled", True]}, 1, 0]}},
        }},
        {"$project": {
            "_id": 0, "key": "$_id", "name": 1, "description": 1, "icon": 1,
            "status": 1, "installations": 1, "enabled_count": 1,
        }},
    ]
    return await db.agents.aggregate(pipeline).to_list(None)


@router.patch("/agents/{agent_key}")
async def update_agent_catalog(agent_key: str, payload: dict, user: dict = Depends(get_superadmin)):
    """Update agent status across all organizations."""
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in {"status", "minimum_plan"}}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    result = await db.agents.update_many({"key": agent_key}, {"$set": allowed})
    await _log_platform(db, user["id"], f"Agent {agent_key} mis à jour",
                          "platform.agent_updated", entity_type="agent",
                          entity_id=agent_key, status="info")
    return {"ok": True, "updated": result.modified_count}


# ---------- Platform settings ----------
@router.get("/platform-settings")
async def get_platform_settings(user: dict = Depends(get_superadmin)):
    db = get_db()
    s = await db.platform_settings.find_one({"id": "platform"}, {"_id": 0})
    if not s:
        s = PlatformSettings().model_dump()
        await db.platform_settings.insert_one(dict(s))
        s = await db.platform_settings.find_one({"id": "platform"}, {"_id": 0})
    return s


PLATFORM_ALLOWED_KEYS = {
    "default_ai_provider", "default_ai_model", "allowed_ai_models",
    "global_ai_daily_budget", "default_test_mode", "maintenance_mode",
    "enabled_integrations", "feature_flags",
}


@router.patch("/platform-settings")
async def update_platform_settings(payload: dict, user: dict = Depends(get_superadmin)):
    db = get_db()
    allowed = {k: v for k, v in payload.items() if k in PLATFORM_ALLOWED_KEYS}
    if not allowed:
        raise HTTPException(400, "Aucun champ autorisé")
    allowed["updated_at"] = now_iso()
    await db.platform_settings.update_one({"id": "platform"}, {"$set": allowed}, upsert=True)
    await _log_platform(db, user["id"], "Configuration plateforme mise à jour",
                          "platform.settings_updated", meta={"fields": list(allowed.keys())},
                          status="info")
    return await db.platform_settings.find_one({"id": "platform"}, {"_id": 0})



# ---------- Safe TEST data cleanup ----------
@router.get("/test-data/cleanup-preview")
async def preview_test_cleanup(user: dict = Depends(get_superadmin)):
    db = get_db()
    explicit_test_orgs = await db.organizations.find({"data_type": "test"}, {"_id": 0, "id": 1, "name": 1}).to_list(None)
    legacy_test_users = await db.users.find({"email": {"$regex": "@example\\.com$", "$options": "i"}}, {"_id": 0, "organization_id": 1}).to_list(None)
    legacy_ids = {u.get("organization_id") for u in legacy_test_users if u.get("organization_id")}
    legacy_orgs = await db.organizations.find({"id": {"$in": list(legacy_ids)}}, {"_id": 0, "id": 1, "name": 1}).to_list(None) if legacy_ids else []
    by_id = {o["id"]: o for o in explicit_test_orgs + legacy_orgs}
    test_orgs = list(by_id.values())
    org_ids = [o["id"] for o in test_orgs if o["id"] != user.get("organization_id")]
    return {
        "organizations": len(org_ids),
        "users": await db.users.count_documents({"organization_id": {"$in": org_ids}}) if org_ids else 0,
        "campaigns": await db.campaigns.count_documents({"organization_id": {"$in": org_ids}}) if org_ids else 0,
        "prospects": await db.prospects.count_documents({"organization_id": {"$in": org_ids}}) if org_ids else 0,
        "messages": await db.messages.count_documents({"organization_id": {"$in": org_ids}}) if org_ids else 0,
        "activities": await db.activities.count_documents({"organization_id": {"$in": org_ids}}) if org_ids else 0,
        "test_organizations": [o for o in test_orgs if o["id"] in org_ids][:50],
    }

@router.post("/test-data/cleanup")
async def cleanup_test_data(payload: dict, user: dict = Depends(get_superadmin)):
    if payload.get("confirm") is not True:
        raise HTTPException(400, "Confirmation explicite requise")
    db = get_db()
    explicit_test_orgs = await db.organizations.find({"data_type": "test"}, {"_id": 0, "id": 1}).to_list(None)
    legacy_test_users = await db.users.find({"email": {"$regex": "@example\\.com$", "$options": "i"}}, {"_id": 0, "organization_id": 1}).to_list(None)
    legacy_ids = {u.get("organization_id") for u in legacy_test_users if u.get("organization_id")}
    legacy_orgs = await db.organizations.find({"id": {"$in": list(legacy_ids)}}, {"_id": 0, "id": 1}).to_list(None) if legacy_ids else []
    by_id = {o["id"]: o for o in explicit_test_orgs + legacy_orgs}
    org_ids = [oid for oid in by_id if oid != user.get("organization_id")]
    if not org_ids:
        return {"ok": True, "deleted": {"organizations": 0}}
    deleted = {}
    for name in ["messages", "prospects", "campaigns", "contacts", "activities", "integrations", "ai_settings", "security_settings", "agents"]:
        res = await getattr(db, name).delete_many({"organization_id": {"$in": org_ids}})
        deleted[name] = res.deleted_count
    res = await db.users.delete_many({"organization_id": {"$in": org_ids}, "id": {"$ne": user["id"]}})
    deleted["users"] = res.deleted_count
    res = await db.organizations.delete_many({"id": {"$in": org_ids}})
    deleted["organizations"] = res.deleted_count
    await _log_platform(db, user["id"], "Données TEST nettoyées", "platform.test_cleanup", meta={"deleted": deleted}, status="warning")
    return {"ok": True, "deleted": deleted}

# ---------- Platform logs ----------
@router.get("/logs")
async def platform_logs(limit: int = 200, user: dict = Depends(get_superadmin)):
    db = get_db()
    return await db.activities.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(None)


# ---------- AI usage across the platform ----------
@router.get("/ai-usage")
async def ai_usage(user: dict = Depends(get_superadmin)):
    db = get_db()
    settings = await db.ai_settings.find({}, {"_id": 0}).to_list(None)
    total_requests = sum(s.get("requests_today", 0) for s in settings)
    total_cost = sum(s.get("cost_today", 0) for s in settings)
    return {
        "total_requests_today": total_requests,
        "total_cost_today": round(total_cost, 4),
        "organizations": [{
            "organization_id": s["organization_id"],
            "provider": s.get("provider"),
            "model": s.get("model"),
            "requests_today": s.get("requests_today", 0),
            "cost_today": s.get("cost_today", 0),
        } for s in settings],
    }
