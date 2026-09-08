"""Phase 0B: simple in-memory rate limiter (per-IP + per-user).

Not intended to be a full DDoS shield — that's a job for an infra layer.
Meant to slow down casual abuse of open endpoints (register/login/campaign).
Cleans up entries lazily on hit.
"""
from __future__ import annotations
import time
from collections import deque
from threading import Lock
from typing import Dict
from fastapi import HTTPException, Request

_buckets: Dict[str, deque] = {}
_lock = Lock()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(key: str, max_calls: int, window_seconds: int) -> None:
    now = time.time()
    with _lock:
        bucket = _buckets.setdefault(key, deque())
        # drop expired
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_calls:
            retry_after = int(bucket[0] + window_seconds - now) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Trop de requêtes. Réessayez dans {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def rate_limit_register(request: Request) -> None:
    limit(f"register:{_client_ip(request)}", max_calls=5, window_seconds=3600)


def rate_limit_login(request: Request) -> None:
    limit(f"login:{_client_ip(request)}", max_calls=10, window_seconds=60)


def rate_limit_campaign(request: Request, org_id: str) -> None:
    limit(f"camp:{org_id}:{_client_ip(request)}", max_calls=20, window_seconds=3600)
