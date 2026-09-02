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
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aura_hub")


async def bootstrap_superadmin():
    """If SUPERADMIN_EMAIL is defined, promote that user to superadmin at startup.
    Safe & idempotent: does nothing if the user does not yet exist."""
    email = os.environ.get("SUPERADMIN_EMAIL", "").strip().lower()
    if not email:
        return
    db = get_db()
    result = await db.users.update_one(
        {"email": email},
        {"$set": {"role": "superadmin"}},
    )
    if result.matched_count:
        logger.info("Bootstrapped superadmin: %s", email)


@app.on_event("startup")
async def startup():
    _ = get_db()  # warm connection
    await bootstrap_superadmin()
    logger.info("Aura Hub API v2 started")


@app.on_event("shutdown")
async def shutdown():
    close_db()
