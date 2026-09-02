"""Auth routes: register, login, me."""
from fastapi import APIRouter, HTTPException, Depends
from models import RegisterRequest, LoginRequest, TokenResponse, User, Organization, UserPublic, SecuritySettings, AISettings, Agent
from auth import hash_password, verify_password, create_access_token, get_current_user
from db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_AGENTS = [
    ("prospect_ai", "Prospect AI", "Recherche et qualification de prospects", "Search", "available", True),
    ("mail_ai", "Mail AI", "Gestion intelligente des emails", "Mail", "coming_soon", False),
    ("admin_ai", "Admin AI", "Assistant administratif", "FileText", "coming_soon", False),
    ("business_ai", "Business AI", "Analyse et optimisation d'entreprise", "TrendingUp", "coming_soon", False),
    ("content_ai", "Content AI", "Création de contenu", "PenLine", "coming_soon", False),
    ("custom_ai", "Custom Agent", "Créer un nouvel agent personnalisé", "Sparkles", "coming_soon", False),
]


async def _seed_org(db, org_id: str) -> None:
    for key, name, desc, icon, status, enabled in DEFAULT_AGENTS:
        agent = Agent(organization_id=org_id, key=key, name=name, description=desc,
                       icon=icon, status=status, enabled=enabled)
        await db.agents.insert_one(agent.model_dump())
    sec = SecuritySettings(organization_id=org_id)
    await db.security_settings.insert_one(sec.model_dump())
    ai = AISettings(organization_id=org_id)
    await db.ai_settings.insert_one(ai.model_dump())


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest):
    db = get_db()
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")

    org = Organization(name=payload.organization_name)
    await db.organizations.insert_one(org.model_dump())

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        organization_id=org.id,
        role="owner",
    )
    await db.users.insert_one(user.model_dump())
    await _seed_org(db, org.id)

    token = create_access_token(user.id, org.id, user.role)
    return TokenResponse(access_token=token, user=UserPublic(**user.model_dump()))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    db = get_db()
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Compte suspendu")
    from models import now_iso
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso()}})
    token = create_access_token(user["id"], user["organization_id"], user["role"])
    return TokenResponse(access_token=token, user=UserPublic(**user))


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**user)


@router.patch("/me")
async def update_me(payload: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    allowed = {k: payload[k] for k in ("full_name", "language", "theme") if k in payload}
    if allowed:
        await db.users.update_one({"id": user["id"]}, {"$set": allowed})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return UserPublic(**updated)
