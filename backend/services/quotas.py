"""Phase 0B: server-side quotas + rate limiting.

Never trust the frontend for quota enforcement. All limits enforced here with
atomic MongoDB counters. Windows: DAILY (UTC day) and MONTHLY (YYYY-MM).
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import HTTPException
from db import get_db

# Default limits (fallback when org.usage_limits is missing a key)
DEFAULT_LIMITS = {
    "daily_provider_searches": 20,
    "monthly_prospects": 1000,
    "monthly_ai_operations": 500,
    "monthly_messages": 300,
}


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _limit_for(org: dict, kind: str) -> int:
    lim = (org or {}).get("usage_limits") or {}
    return int(lim.get(kind, DEFAULT_LIMITS.get(kind, 0)))


async def _get_counter(org_id: str, kind: str, window: str) -> int:
    db = get_db()
    doc = await db.usage_counters.find_one(
        {"organization_id": org_id, "kind": kind, "window": window}, {"_id": 0, "count": 1}
    )
    return int((doc or {}).get("count", 0))


async def _atomic_increment(org_id: str, kind: str, window: str, delta: int = 1) -> int:
    """Atomic $inc; upsert; returns new count."""
    db = get_db()
    res = await db.usage_counters.find_one_and_update(
        {"organization_id": org_id, "kind": kind, "window": window},
        {"$inc": {"count": delta}, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
        return_document=True,
    )
    # find_one_and_update in motor returns the DOC after update by default only with ReturnDocument.AFTER,
    # so fall back to a plain read if needed
    if res is None or "count" not in (res or {}):
        return await _get_counter(org_id, kind, window)
    return int(res.get("count", 0))


async def check_provider_search(org: dict) -> None:
    """Enforce daily_provider_searches BEFORE running the provider call."""
    limit = _limit_for(org, "daily_provider_searches")
    if limit <= 0:
        return
    current = await _get_counter(org["id"], "provider_search", _today_utc())
    if current >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Quota atteint : {current}/{limit} recherches provider aujourd'hui. "
                    "Réessayez demain ou passez à un plan supérieur."
        )


async def record_provider_search(org: dict) -> int:
    return await _atomic_increment(org["id"], "provider_search", _today_utc(), 1)


async def check_prospects_add(org: dict, count: int) -> None:
    """Enforce monthly_prospects BEFORE inserting new prospects."""
    limit = _limit_for(org, "monthly_prospects")
    if limit <= 0 or count <= 0:
        return
    current = await _get_counter(org["id"], "prospect", _month_utc())
    if current + count > limit:
        remaining = max(0, limit - current)
        raise HTTPException(
            status_code=429,
            detail=f"Quota atteint : {current}/{limit} prospects ce mois. "
                    f"Il vous reste {remaining} prospect(s). Passez à un plan supérieur pour continuer."
        )


async def record_prospects_added(org: dict, count: int) -> int:
    if count <= 0:
        return 0
    return await _atomic_increment(org["id"], "prospect", _month_utc(), count)


async def check_and_record_ai(org: dict) -> None:
    """Enforce monthly_ai_operations and increment atomically (fail-open on race
    isn't a concern since we check-then-inc; slight over-shoot by 1 acceptable)."""
    limit = _limit_for(org, "monthly_ai_operations")
    if limit <= 0:
        return
    current = await _get_counter(org["id"], "ai_op", _month_utc())
    if current >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Quota atteint : {current}/{limit} opérations IA ce mois."
        )
    await _atomic_increment(org["id"], "ai_op", _month_utc(), 1)


async def check_messages_send(org: dict) -> None:
    limit = _limit_for(org, "monthly_messages")
    if limit <= 0:
        return
    current = await _get_counter(org["id"], "message_send", _month_utc())
    if current >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Quota atteint : {current}/{limit} messages envoyés ce mois."
        )


async def record_message_sent(org: dict) -> int:
    return await _atomic_increment(org["id"], "message_send", _month_utc(), 1)


async def usage_summary(org: dict) -> dict:
    """Return current usage for the UI."""
    return {
        "provider_search_today": await _get_counter(org["id"], "provider_search", _today_utc()),
        "prospects_this_month": await _get_counter(org["id"], "prospect", _month_utc()),
        "ai_ops_this_month": await _get_counter(org["id"], "ai_op", _month_utc()),
        "messages_this_month": await _get_counter(org["id"], "message_send", _month_utc()),
        "limits": {k: _limit_for(org, k) for k in DEFAULT_LIMITS.keys()},
    }
