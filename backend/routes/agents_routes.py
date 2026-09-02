"""Agent routes."""
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.agents.find({"organization_id": user["organization_id"]}, {"_id": 0})
    return await cursor.to_list(length=None)


@router.patch("/{agent_key}")
async def update_agent(agent_key: str, payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: payload[k] for k in ("enabled",) if k in payload}
    result = await db.agents.update_one(
        {"organization_id": user["organization_id"], "key": agent_key},
        {"$set": allowed},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Agent introuvable")
    return await db.agents.find_one(
        {"organization_id": user["organization_id"], "key": agent_key}, {"_id": 0}
    )
