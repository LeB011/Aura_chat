"""Aura Hub - main FastAPI entry (V2)."""
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from db import get_db, close_db  # noqa: E402
from routes.auth_routes import router as auth_router  # noqa: E402
from routes.agents_routes import router as agents_router  # noqa: E402
from routes.prospects_routes import router as prospects_router  # noqa: E402
from routes.messages_routes import router as messages_router  # noqa: E402
from routes.misc_routes import (activities_router, security_router,  # noqa: E402
                                  integrations_router, settings_router,
                                  analytics_router, demo_router)
from routes.admin_routes import router as admin_router  # noqa: E402

app = FastAPI(title="Aura Hub API", version="2.0.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "Aura Hub API", "status": "ok", "version": "2.0.0"}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


# Mount feature routers
for r in (auth_router, agents_router, prospects_router, messages_router,
           activities_router, security_router, integrations_router,
           settings_router, analytics_router, demo_router, admin_router):
    api_router.include_router(r)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    # Phase 0B: use explicit CORS_ORIGINS from env in production.
    # Fallback to "*" ONLY when the env var is unset OR the platform is running
    # in local/dev mode. Never mix explicit origins with "*" (browsers reject it).
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()] or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aura_hub")


DEFAULT_SUPERADMIN_EMAILS = {"infoitpro078@gmail.com"}


def _superadmin_emails() -> set[str]:
    """Return the platform-owner allowlist used only for startup promotion.

    - `SUPERADMIN_EMAIL` keeps backwards compatibility.
    - `SUPERADMIN_EMAILS` accepts a comma-separated list for future owners/admins.
    - The Aura_chat owner account is included explicitly so this Render codebase
      always restores the requested Super Admin access after a redeploy.
    """
    emails = set(DEFAULT_SUPERADMIN_EMAILS)
    single = os.environ.get("SUPERADMIN_EMAIL", "").strip().lower()
    if single:
        emails.add(single)
    many = os.environ.get("SUPERADMIN_EMAILS", "")
    emails.update(e.strip().lower() for e in many.split(",") if e.strip())
    return emails


async def bootstrap_superadmin():
    """Promote existing allow-listed users to superadmin at startup.

    Safe & idempotent: it never creates an account and therefore only promotes
    a user that already exists in Aura_chat's database.
    """
    db = get_db()
    for email in sorted(_superadmin_emails()):
        result = await db.users.update_one(
            {"email": email},
            {"$set": {"role": "superadmin"}},
        )
        if result.matched_count:
            logger.info("Bootstrapped superadmin: %s", email)


async def ensure_indexes():
    """Phase 0: enforce email uniqueness + hot query indexes."""
    db = get_db()
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("organization_id")
        await db.prospects.create_index([("organization_id", 1), ("created_at", -1)])
        await db.campaigns.create_index([("organization_id", 1), ("created_at", -1)])
        await db.messages.create_index([("organization_id", 1), ("prospect_id", 1)])
        await db.activities.create_index([("organization_id", 1), ("created_at", -1)])
        await db.agents.create_index([("organization_id", 1), ("key", 1)], unique=True)
        # Phase 0B: quota counters index
        await db.usage_counters.create_index(
            [("organization_id", 1), ("kind", 1), ("window", 1)], unique=True
        )
        logger.info("Indexes ensured")
    except Exception as e:  # index might already exist with different opts
        logger.warning("ensure_indexes: %s", e)


@app.on_event("startup")
async def startup():
    _ = get_db()  # warm connection
    await ensure_indexes()
    await bootstrap_superadmin()
    logger.info("Aura Hub API v2 started")


@app.on_event("shutdown")
async def shutdown():
    close_db()
