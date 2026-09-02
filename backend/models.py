"""Pydantic models for Aura Hub V2. All IDs are UUID strings for portability."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


class TimestampedModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


# ------------------ Tenancy / Auth ------------------
class Organization(TimestampedModel):
    name: str
    plan: Literal["demo", "starter", "business", "premium"] = "demo"
    plan_status: Literal["active", "trial", "past_due", "suspended", "canceled"] = "active"
    suspended: bool = False
    country: str = "CH"
    test_mode: bool = True
    data_type: Literal["real", "demo", "test"] = "real"
    usage_limits: dict = Field(default_factory=lambda: {
        "monthly_prospects": 1000,
        "monthly_ai_operations": 500,
        "monthly_messages": 300,
        "daily_provider_searches": 20,
        "max_results_per_search": 50,
    })


class User(TimestampedModel):
    email: EmailStr
    password_hash: str
    full_name: str
    organization_id: str
    role: Literal["superadmin", "owner", "admin", "member"] = "owner"
    language: Literal["fr", "en"] = "fr"
    theme: Literal["light", "dark"] = "light"
    suspended: bool = False
    last_login_at: Optional[str] = None
    data_type: Literal["real", "demo", "test"] = "real"


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    organization_id: str
    role: str
    language: str
    theme: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    organization_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ------------------ Agents ------------------
class Agent(TimestampedModel):
    organization_id: str
    key: str  # "prospect_ai", "mail_ai", ...
    name: str
    description: str
    icon: str
    status: Literal["available", "coming_soon", "beta", "disabled"] = "coming_soon"
    enabled: bool = False
    minimum_plan: Literal["demo", "starter", "business", "premium"] = "demo"
    last_activity_at: Optional[str] = None


# ------------------ Prospect AI ------------------
class SearchCriteria(BaseModel):
    campaign_name: str
    industry: str
    country: str = "CH"
    canton: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    radius_km: Optional[int] = 20
    max_results: int = 25
    sources: List[str] = Field(default_factory=lambda: ["search_engines", "directories"])
    provider: str = "mock"  # V2: explicit provider selection
    filters: dict = Field(default_factory=dict)
    ai_analysis_enabled: bool = True
    service_to_sell: List[str] = Field(default_factory=list)
    service_notes: Optional[str] = None
    language: Literal["auto", "fr", "de", "it", "en", "es"] = "auto"
    min_score: int = 0  # V2: qualification threshold
    offer: Optional[dict] = None  # Campaign commercial offer/configuration


class CampaignOffer(BaseModel):
    """What the sender is offering — used to personalize outreach messages."""
    product_name: Optional[str] = None
    description: Optional[str] = None  # what we sell
    main_benefit: Optional[str] = None
    target_customer: Optional[str] = None
    price: Optional[str] = None
    special_offer: Optional[str] = None
    differentiator: Optional[str] = None
    cta_preference: Optional[str] = None  # e.g. "send_example", "demo", "call", "reply"
    sender_name: Optional[str] = None
    brand: Optional[str] = None
    signature: Optional[str] = None
    website: Optional[str] = None


class Campaign(TimestampedModel):
    organization_id: str
    user_id: str
    name: str
    criteria: SearchCriteria
    status: Literal["draft", "active", "paused", "done", "archived"] = "active"
    mode: Literal["manual", "validation", "automated"] = "validation"
    provider_used: str = "mock"
    offer: Optional[CampaignOffer] = None
    stats: dict = Field(default_factory=lambda: {
        "prospects_found": 0,
        "qualified": 0,
        "to_contact": 0,
        "messages_prepared": 0,
        "messages_sent": 0,
        "replies": 0,
        "meetings": 0,
        "customers": 0,
    })


class AIAnalysis(BaseModel):
    summary: Optional[str] = None
    main_activity: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    likely_customers: Optional[str] = None
    digital_maturity: Optional[str] = None
    opportunities: List[str] = Field(default_factory=list)
    problems: List[str] = Field(default_factory=list)
    ai_use_cases: List[str] = Field(default_factory=list)
    sales_arguments: List[str] = Field(default_factory=list)
    relevance_note: Optional[str] = None
    ai_opportunity_score: int = 0  # 0-100, legacy alias
    confidence_score: int = 0  # 0-100
    is_hypothesis: bool = True


PROSPECT_STATUSES = [
    "new", "to_analyze", "analyzed", "to_contact", "message_ready",
    "validated", "contacted", "replied", "interested", "meeting",
    "customer", "refused", "do_not_contact"
]

QUALIFICATION_STATUSES = ["unqualified", "low", "medium", "good", "excellent"]


class Prospect(TimestampedModel):
    organization_id: str
    campaign_id: Optional[str] = None
    company_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    canton: Optional[str] = None
    country: str = "CH"

    # Source metadata
    source: str = "mock"
    source_url: Optional[str] = None
    source_provider: str = "mock"
    source_date: str = Field(default_factory=now_iso)
    date_found: str = Field(default_factory=now_iso)
    external_id: Optional[str] = None  # e.g. Google place_id
    retrieved_at: Optional[str] = None
    data_type: Literal["real", "demo", "test"] = "real"

    # Verification (V2)
    verified_fields: List[str] = Field(default_factory=list)   # e.g. ["company_name","city","website"]
    unverified_fields: List[str] = Field(default_factory=list) # inferred by AI

    # Contact metadata (V2)
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None

    # Explainable qualification (V2)
    qualification_score: int = 0  # 0-100
    qualification_confidence: int = 0  # 0-100
    qualification_status: str = "unqualified"  # low/medium/good/excellent
    qualification_reasons: List[dict] = Field(default_factory=list)  # [{delta, label, evidence}]

    # Compliance metadata (V2)
    do_not_contact: bool = False
    opted_out: bool = False
    existing_customer: bool = False
    professional_relevance: Optional[str] = None
    compliance_status: Literal["low_risk", "review_required", "blocked", "unknown"] = "unknown"
    compliance_notes: Optional[str] = None

    # Operational status
    status: str = "new"
    ai_analysis: Optional[AIAnalysis] = None
    notes: List[dict] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    last_contact_at: Optional[str] = None
    is_demo: bool = False


class ProspectUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Optional[str] = None
    notes: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None
    do_not_contact: Optional[bool] = None
    opted_out: Optional[bool] = None
    existing_customer: Optional[bool] = None


# ------------------ Messages ------------------
MESSAGE_STATUSES = ["draft", "needs_review", "approved", "rejected", "sent", "failed", "test", "opt_out", "blocked"]


class Message(TimestampedModel):
    organization_id: str
    prospect_id: str
    channel: Literal["email", "phone", "linkedin", "whatsapp", "other"] = "email"
    tone: str = "professional"
    length: str = "normal"
    language: str = "auto"
    objective: str = "presentation"
    subject: Optional[str] = None
    body: str
    cta: Optional[str] = None
    status: str = "draft"
    sent_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_reason: Optional[str] = None


class MessageGenerateRequest(BaseModel):
    prospect_id: str
    channel: Literal["email", "phone", "linkedin", "whatsapp", "other"] = "email"
    tone: str = "professional"
    length: str = "normal"
    language: str = "auto"
    objective: str = "presentation"
    strategy: Literal["direct_short", "professional", "consultative"] = "professional"


# ------------------ Activity / Audit ------------------
class Activity(TimestampedModel):
    organization_id: Optional[str] = None  # None = platform-level (super admin)
    user_id: Optional[str] = None
    agent_key: str = "prospect_ai"
    action: str
    action_type: str = "generic"  # e.g. campaign.created, prospect.qualified, security.setting_changed
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    target: Optional[str] = None
    result: Optional[str] = None
    status: Literal["info", "success", "warning", "error"] = "info"
    meta: dict = Field(default_factory=dict)


# ------------------ Security ------------------
class SecuritySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    organization_id: str
    human_approval_required: bool = True
    daily_sending_limit: int = 20
    hourly_sending_limit: int = 5
    delay_between_messages_minutes: int = 5
    random_delay: bool = True
    duplicate_protection: bool = True
    existing_customer_exclusion: bool = True
    dnc_list_enabled: bool = True
    unsubscribe_protection: bool = True
    invalid_email_protection: bool = True
    generic_email_warning: bool = True
    personal_email_warning: bool = True
    require_professional_relevance: bool = True
    confidence_threshold: int = 60
    ai_hallucination_protection: bool = True
    sensitive_industry_protection: bool = True
    compliance_review_required: bool = True
    kill_switch_active: bool = False
    blacklist: dict = Field(default_factory=lambda: {"companies": [], "emails": [], "domains": [], "cities": [], "sectors": []})
    updated_at: str = Field(default_factory=now_iso)


# ------------------ Integrations & AI Settings ------------------
class Integration(TimestampedModel):
    organization_id: str
    key: str
    name: str
    status: Literal["not_configured", "configured", "connected", "error"] = "not_configured"
    connected: bool = False
    config: dict = Field(default_factory=dict)
    last_error: Optional[str] = None


class AISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    organization_id: str
    provider: str = "openai"
    model: str = "gpt-5.4"
    creativity: float = 0.5
    language: str = "fr"
    max_cost_per_operation: float = 0.5
    max_daily_usage: float = 20.0
    requests_today: int = 0
    tokens_today: int = 0
    cost_today: float = 0.0
    last_reset_day: str = Field(default_factory=lambda: now_iso()[:10])
    updated_at: str = Field(default_factory=now_iso)


# ------------------ Platform (Super Admin) ------------------
class PlatformSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "platform"
    default_ai_provider: str = "openai"
    default_ai_model: str = "gpt-5.4"
    allowed_ai_models: List[str] = Field(default_factory=lambda: ["gpt-5.4", "gpt-5.4-mini", "claude-sonnet-4.6"])
    global_ai_daily_budget: float = 100.0
    default_test_mode: bool = True
    maintenance_mode: bool = False
    enabled_integrations: List[str] = Field(default_factory=lambda: ["openai", "csv", "webhook"])
    feature_flags: dict = Field(default_factory=dict)
    updated_at: str = Field(default_factory=now_iso)
