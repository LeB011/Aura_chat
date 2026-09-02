"""Message generation + list routes."""
from fastapi import APIRouter, Depends, HTTPException
from models import Message, MessageGenerateRequest, Activity, now_iso
from auth import get_current_user
from db import get_db
from services.ai_service import generate_message

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/generate")
async def generate(payload: MessageGenerateRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    prospect = await db.prospects.find_one({"id": payload.prospect_id, "organization_id": user["organization_id"]}, {"_id": 0})
    if not prospect:
        raise HTTPException(404, "Prospect introuvable")
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})
    test_mode = bool(org.get("test_mode", True)) if org else True
    ai_settings = await db.ai_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
    model = (ai_settings or {}).get("model", "gpt-5.4")

    campaign = None
    if prospect.get("campaign_id"):
        campaign = await db.campaigns.find_one({"id": prospect["campaign_id"]}, {"_id": 0})
    service_notes = (campaign or {}).get("criteria", {}).get("service_notes") if campaign else None
    offer = (campaign or {}).get("offer") or (campaign or {}).get("criteria", {}).get("offer") or {}

    result = await generate_message(prospect, payload.channel, payload.tone, payload.length,
                                     payload.language, payload.objective, service_notes,
                                     test_mode=test_mode, model=model, offer=offer,
                                     strategy=payload.strategy)

    msg = Message(
        organization_id=user["organization_id"],
        prospect_id=payload.prospect_id,
        channel=payload.channel,
        tone=payload.tone,
        length=payload.length,
        language=payload.language,
        objective=payload.objective,
        subject=result.get("subject"),
        body=result.get("body", ""),
        cta=result.get("cta"),
        status="draft",
    )
    await db.messages.insert_one(msg.model_dump())

    # Update prospect
    await db.prospects.update_one(
        {"id": payload.prospect_id},
        {"$set": {"status": "message_ready", "updated_at": now_iso()}},
    )

    # Log
    act = Activity(organization_id=user["organization_id"],
                    action=f"Message {payload.channel} généré",
                    target=prospect.get("company_name"), status="success")
    await db.activities.insert_one(act.model_dump())
    return msg.model_dump()


@router.get("")
async def list_messages(prospect_id: str = None, user: dict = Depends(get_current_user)):
    db = get_db()
    q = {"organization_id": user["organization_id"]}
    if prospect_id:
        q["prospect_id"] = prospect_id
    return await db.messages.find(q, {"_id": 0}).sort("created_at", -1).to_list(None)


@router.patch("/{message_id}")
async def update_message(message_id: str, payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: payload[k] for k in ("subject", "body", "cta", "status") if k in payload}
    if not allowed:
        raise HTTPException(400, "Aucun changement")
    # Enforce kill switch when setting status to 'sent'
    if allowed.get("status") == "sent":
        security = await db.security_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
        if security and security.get("kill_switch_active"):
            raise HTTPException(403, "Kill switch actif : envoi bloqué")
        allowed["sent_at"] = now_iso()
    allowed["updated_at"] = now_iso()
    await db.messages.update_one(
        {"id": message_id, "organization_id": user["organization_id"]},
        {"$set": allowed},
    )
    return await db.messages.find_one({"id": message_id, "organization_id": user["organization_id"]}, {"_id": 0})


@router.post("/{message_id}/send")
async def send_message(message_id: str, user: dict = Depends(get_current_user)):
    """In V1 this only simulates send when test_mode ON. Otherwise marks as sent (no real SMTP)."""
    db = get_db()
    msg = await db.messages.find_one({"id": message_id, "organization_id": user["organization_id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message introuvable")
    security = await db.security_settings.find_one({"organization_id": user["organization_id"]}, {"_id": 0})
    if security and security.get("kill_switch_active"):
        raise HTTPException(403, "Kill switch actif : envoi bloqué")
    org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})
    test_mode = bool(org.get("test_mode", True)) if org else True

    # V2.1 has no real delivery transport. Never pretend an email was sent.
    if not test_mode:
        raise HTTPException(501, "Aucun transport email réel n'est configuré. Le message reste en brouillon.")
    await db.messages.update_one(
        {"id": message_id, "organization_id": user["organization_id"]},
        {"$set": {"status": "test", "updated_at": now_iso()}},
    )
    act = Activity(organization_id=user["organization_id"], action="Envoi simulé (Test Mode)",
                    target=msg.get("subject") or msg.get("body", "")[:50], status="success")
    await db.activities.insert_one(act.model_dump())
    return {"ok": True, "test_mode": True, "sent": False}
