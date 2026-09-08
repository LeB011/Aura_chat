"""Agent routes.

Phase 0 hardening (2026-09-08):
- Ordinary client users can VIEW agents but cannot self-enable a locked agent.
- Enabling/disabling an agent for an organization is now Super Admin only
  (moved to /api/admin/organizations/{id}/agents/{key} and
  /api/admin/agents/{key} in admin_routes).
- This file exposes read-only agent info + a lightweight entitlement summary.
"""
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user, PLAN_HIERARCHY
from db import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.agents.find({"organization_id": user["organization_id"]}, {"_id": 0})
    agents = await cursor.to_list(length=None)
    # Add computed `accessible` flag so the UI can grey out locked agents
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0}) or {}
    plan = org.get("plan", "demo")
    plan_status = org.get("plan_status", "active")
    for a in agents:
        status_ok = a.get("status") in ("available", "beta")
        plan_ok = PLAN_HIERARCHY.get(plan, 0) >= PLAN_HIERARCHY.get(a.get("minimum_plan", "demo"), 0)
        status_active = plan_status in ("active", "trial")
        a["accessible"] = bool(status_ok and a.get("enabled") and plan_ok and status_active)
    return agents


@router.get("/{agent_key}/entitlement")
async def agent_entitlement(agent_key: str, user: dict = Depends(get_current_user)):
    """Read-only entitlement check for the UI (never grants access)."""
    db = get_db()
    agent = await db.agents.find_one(
        {"organization_id": user["organization_id"], "key": agent_key}, {"_id": 0}
    )
    if not agent:
        raise HTTPException(404, "Agent introuvable")
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0}) or {}
    plan = org.get("plan", "demo")
    min_plan = agent.get("minimum_plan", "demo")
    status_ok = agent.get("status") in ("available", "beta")
    plan_ok = PLAN_HIERARCHY.get(plan, 0) >= PLAN_HIERARCHY.get(min_plan, 0)
    plan_status_ok = org.get("plan_status", "active") in ("active", "trial")
    reasons = []
    if not status_ok:
        reasons.append(f"Agent en statut '{agent.get('status')}'")
    if not agent.get("enabled"):
        reasons.append("Agent non activé pour cette organisation")
    if not plan_ok:
        reasons.append(f"Plan '{plan}' inférieur au minimum requis '{min_plan}'")
    if not plan_status_ok:
        reasons.append(f"Statut abonnement: {org.get('plan_status')}")

    return {
        "agent_key": agent_key,
        "accessible": status_ok and agent.get("enabled") and plan_ok and plan_status_ok,
        "status": agent.get("status"),
        "enabled": bool(agent.get("enabled")),
        "minimum_plan": min_plan,
        "current_plan": plan,
        "reasons": reasons,
    }
