"""JWT authentication utilities. Multi-tenant with organization isolation and RBAC."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_db

_bearer = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {"member": 0, "admin": 1, "owner": 2, "superadmin": 3}


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _algo() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, organization_id: str, role: str) -> str:
    expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=_algo())


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[_algo()])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Compte suspendu")
    # Verify organization is not suspended (except superadmin)
    if user.get("role") != "superadmin":
        org = await db.organizations.find_one({"id": user["organization_id"]}, {"_id": 0})
        if org and org.get("suspended"):
            raise HTTPException(status_code=403, detail="Organisation suspendue")
    return user


def require_min_role(min_role: str):
    """Guard a route by minimum role: member < admin < owner < superadmin."""
    min_level = ROLE_HIERARCHY.get(min_role, 0)

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        level = ROLE_HIERARCHY.get(user.get("role", "member"), 0)
        if level < min_level:
            raise HTTPException(status_code=403, detail="Permissions insuffisantes")
        return user
    return _check


def require_role(*allowed_roles: str):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _check


async def get_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs de la plateforme")
    return user
