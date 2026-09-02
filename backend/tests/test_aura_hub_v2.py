"""Aura Hub V2 backend tests — super admin, RBAC, provider selection,
explainable scoring, CSV import, kill-switch, audit logs, isolation."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prospect-ai-hub-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@aurahub.io"
DEMO_PASSWORD = "Aura2026!"


# ---------- Helpers ----------
def _register_or_login(s, email, password, full_name="Test User", org_name="Test Org"):
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": password,
        "full_name": full_name, "organization_name": org_name,
    })
    if r.status_code == 200:
        return r.json()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def demo(s):
    return _register_or_login(s, DEMO_EMAIL, DEMO_PASSWORD, "Demo User", "Aura Demo SA")


@pytest.fixture(scope="session")
def demo_h(demo):
    return {"Authorization": f"Bearer {demo['access_token']}"}


@pytest.fixture(scope="session")
def second(s):
    email = f"v2tenant_{uuid.uuid4().hex[:8]}@example.com"
    return _register_or_login(s, email, "Second2026!", "V2 Second", "V2 Second Org")


@pytest.fixture(scope="session")
def second_h(second):
    return {"Authorization": f"Bearer {second['access_token']}"}


# ------------- Super admin access control -------------
class TestSuperAdminAccess:
    def test_demo_is_superadmin(self, s, demo_h):
        r = s.get(f"{API}/auth/me", headers=demo_h)
        assert r.status_code == 200
        assert r.json()["role"] == "superadmin"

    def test_second_user_cannot_access_admin(self, s, second_h):
        endpoints = [
            "/admin/overview", "/admin/organizations", "/admin/users",
            "/admin/platform-settings", "/admin/agents", "/admin/logs",
            "/admin/ai-usage",
        ]
        for e in endpoints:
            r = s.get(f"{API}{e}", headers=second_h)
            assert r.status_code == 403, f"{e} returned {r.status_code}"

    def test_unauthenticated_admin_401(self, s):
        r = s.get(f"{API}/admin/overview")
        assert r.status_code == 401


# ------------- Overview -------------
class TestSuperAdminOverview:
    def test_overview_keys(self, s, demo_h):
        r = s.get(f"{API}/admin/overview", headers=demo_h)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total_organizations", "active_organizations", "suspended_organizations",
                  "total_users", "total_prospects", "prospects_today", "total_campaigns",
                  "active_agents", "messages_prepared", "messages_sent", "errors_recent",
                  "ai_operations_estimated", "recent_activity"):
            assert k in d, f"missing {k}"
        assert isinstance(d["recent_activity"], list)


# ------------- Organizations -------------
class TestSuperAdminOrgs:
    def test_list_orgs(self, s, demo_h, second):
        r = s.get(f"{API}/admin/organizations", headers=demo_h)
        assert r.status_code == 200
        orgs = r.json()
        assert len(orgs) >= 2
        for o in orgs:
            assert "users_count" in o and "prospects_count" in o and "campaigns_count" in o

    def test_get_org_excludes_password(self, s, demo_h, second):
        org_id = second["user"]["organization_id"]
        r = s.get(f"{API}/admin/organizations/{org_id}", headers=demo_h)
        assert r.status_code == 200
        d = r.json()
        assert "users" in d and isinstance(d["users"], list)
        for u in d["users"]:
            assert "password_hash" not in u

    def test_patch_org_allowed(self, s, demo_h, second):
        org_id = second["user"]["organization_id"]
        r = s.patch(f"{API}/admin/organizations/{org_id}", headers=demo_h,
                    json={"name": "V2 Second Org (Renamed)", "unknown_key": "ignored"})
        assert r.status_code == 200
        assert r.json()["name"] == "V2 Second Org (Renamed)"

    def test_patch_org_empty_400(self, s, demo_h, second):
        org_id = second["user"]["organization_id"]
        r = s.patch(f"{API}/admin/organizations/{org_id}", headers=demo_h,
                    json={"unknown_only": "x"})
        assert r.status_code == 400


# ------------- Suspend / reactivate flow -------------
class TestSuspendFlow:
    def test_suspend_and_reactivate(self, s):
        # Create a fresh org just for this test to avoid impacting other tests
        email = f"suspend_{uuid.uuid4().hex[:8]}@example.com"
        data = _register_or_login(s, email, "Suspend2026!", "Suspend User", "Suspend Org")
        org_id = data["user"]["organization_id"]
        tok = data["access_token"]
        h = {"Authorization": f"Bearer {tok}"}

        # Baseline access works
        assert s.get(f"{API}/auth/me", headers=h).status_code == 200

        # Login as superadmin, suspend org
        demo_login = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).json()
        sa_h = {"Authorization": f"Bearer {demo_login['access_token']}"}
        r = s.post(f"{API}/admin/organizations/{org_id}/suspend", headers=sa_h)
        assert r.status_code == 200

        # Now the org owner is blocked
        blocked = s.get(f"{API}/auth/me", headers=h)
        assert blocked.status_code == 403
        assert "suspend" in blocked.json().get("detail", "").lower()

        # Reactivate
        r = s.post(f"{API}/admin/organizations/{org_id}/reactivate", headers=sa_h)
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me", headers=h).status_code == 200


# ------------- Users -------------
class TestSuperAdminUsers:
    def test_list_users_no_hash(self, s, demo_h):
        r = s.get(f"{API}/admin/users", headers=demo_h)
        assert r.status_code == 200
        users = r.json()
        for u in users:
            assert "password_hash" not in u

    def test_patch_user_role(self, s, demo_h, second):
        uid = second["user"]["id"]
        r = s.patch(f"{API}/admin/users/{uid}", headers=demo_h, json={"role": "admin"})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "admin"
        # Restore
        s.patch(f"{API}/admin/users/{uid}", headers=demo_h, json={"role": "owner"})

    def test_patch_user_invalid_role(self, s, demo_h, second):
        uid = second["user"]["id"]
        r = s.patch(f"{API}/admin/users/{uid}", headers=demo_h, json={"role": "hacker"})
        assert r.status_code == 400

    def test_patch_user_suspend_blocks_calls(self, s, demo_h):
        # Create fresh user
        email = f"tosuspend_{uuid.uuid4().hex[:8]}@example.com"
        data = _register_or_login(s, email, "Sup2026!", "Bob", "BobOrg")
        h = {"Authorization": f"Bearer {data['access_token']}"}
        uid = data["user"]["id"]
        assert s.get(f"{API}/auth/me", headers=h).status_code == 200
        r = s.patch(f"{API}/admin/users/{uid}", headers=demo_h, json={"suspended": True})
        assert r.status_code == 200
        blocked = s.get(f"{API}/auth/me", headers=h)
        assert blocked.status_code == 403


# ------------- Platform settings -------------
class TestPlatformSettings:
    def test_get_creates_if_missing(self, s, demo_h):
        r = s.get(f"{API}/admin/platform-settings", headers=demo_h)
        assert r.status_code == 200
        d = r.json()
        assert d is not None
        assert d.get("id") == "platform"

    def test_patch_allowlist(self, s, demo_h):
        r = s.patch(f"{API}/admin/platform-settings", headers=demo_h,
                    json={"maintenance_mode": False, "hacky": "value"})
        assert r.status_code == 200
        assert r.json()["maintenance_mode"] is False

    def test_patch_empty_400(self, s, demo_h):
        r = s.patch(f"{API}/admin/platform-settings", headers=demo_h,
                    json={"only_unknown": True})
        assert r.status_code == 400


# ------------- Agents catalog -------------
class TestAgentsCatalog:
    def test_catalog(self, s, demo_h):
        r = s.get(f"{API}/admin/agents", headers=demo_h)
        assert r.status_code == 200
        agents = r.json()
        keys = {a["_id"] for a in agents}
        assert "prospect_ai" in keys
        pa = next(a for a in agents if a["_id"] == "prospect_ai")
        assert "installations" in pa and "enabled_count" in pa

    def test_patch_agent_status(self, s, demo_h):
        r = s.patch(f"{API}/admin/agents/prospect_ai", headers=demo_h,
                    json={"status": "beta"})
        assert r.status_code == 200
        assert r.json()["updated"] >= 1
        # Restore
        s.patch(f"{API}/admin/agents/prospect_ai", headers=demo_h, json={"status": "available"})


# ------------- Logs & AI usage -------------
class TestLogsUsage:
    def test_logs(self, s, demo_h):
        r = s.get(f"{API}/admin/logs", headers=demo_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_ai_usage(self, s, demo_h):
        r = s.get(f"{API}/admin/ai-usage", headers=demo_h)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_requests_today", "total_cost_today", "organizations"):
            assert k in d


# ------------- Multi-tenant V2 isolation -------------
class TestIsolation:
    def test_second_org_cannot_access_first(self, s, demo_h, second_h):
        # Create in demo org
        r = s.post(f"{API}/campaigns", headers=demo_h, json={
            "campaign_name": f"TEST_Iso2_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien", "country": "CH", "city": "Lausanne",
            "max_results": 3, "ai_analysis_enabled": True,
        })
        assert r.status_code == 200
        camp_id = r.json()["campaign"]["id"]

        # second cannot list this campaign
        s_camps = s.get(f"{API}/campaigns", headers=second_h).json()
        assert all(c["id"] != camp_id for c in s_camps)

        # second cannot GET first-org campaign by id
        r2 = s.get(f"{API}/campaigns/{camp_id}", headers=second_h)
        assert r2.status_code == 404

        # And no prospects
        assert s.get(f"{API}/prospects?campaign_id={camp_id}", headers=second_h).json() == []


# ------------- Explainable scoring -------------
class TestExplainableScoring:
    def test_campaign_prospects_have_reasons(self, s, demo_h):
        r = s.post(f"{API}/campaigns", headers=demo_h, json={
            "campaign_name": f"TEST_Explain_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien", "country": "CH", "city": "Lausanne",
            "max_results": 4, "ai_analysis_enabled": True,
        })
        assert r.status_code == 200, r.text
        cid = r.json()["campaign"]["id"]
        prospects = s.get(f"{API}/prospects?campaign_id={cid}", headers=demo_h).json()
        assert len(prospects) > 0
        for p in prospects:
            assert 0 <= p["qualification_score"] <= 100
            assert p["qualification_status"] in {"low", "medium", "good", "excellent", "unqualified"}
            assert 0 <= p["qualification_confidence"] <= 100
            assert isinstance(p["qualification_reasons"], list) and len(p["qualification_reasons"]) > 0
            for reason in p["qualification_reasons"]:
                assert set(reason.keys()) >= {"delta", "label", "evidence"}
            assert len(p["verified_fields"]) > 0
            assert len(p["unverified_fields"]) > 0


# ------------- Provider selection -------------
class TestProviders:
    def test_provider_list_flags(self, s, demo_h):
        r = s.get(f"{API}/prospect-sources", headers=demo_h)
        assert r.status_code == 200
        by_key = {p["key"]: p for p in r.json()}
        assert by_key["mock"]["is_configured"] is True
        assert by_key["google_places"]["is_configured"] is False
        assert by_key["custom_api"]["is_configured"] is False

    def test_mock_works(self, s, demo_h):
        r = s.post(f"{API}/campaigns", headers=demo_h, json={
            "campaign_name": f"TEST_ProvMock_{uuid.uuid4().hex[:6]}",
            "industry": "Peintre", "country": "CH", "city": "Genève",
            "max_results": 2, "ai_analysis_enabled": False, "provider": "mock",
        })
        assert r.status_code == 200
        assert r.json()["campaign"]["provider_used"] == "mock"

    def test_google_places_falls_back_in_test_mode(self, s, demo_h):
        # Ensure test_mode is ON
        s.patch(f"{API}/settings/organization", headers=demo_h, json={"test_mode": True})
        r = s.post(f"{API}/campaigns", headers=demo_h, json={
            "campaign_name": f"TEST_ProvGP_{uuid.uuid4().hex[:6]}",
            "industry": "Peintre", "country": "CH", "city": "Genève",
            "max_results": 2, "ai_analysis_enabled": False, "provider": "google_places",
        })
        assert r.status_code == 200
        assert r.json()["campaign"]["provider_used"] == "mock"

    def test_google_places_rejected_without_config_when_test_mode_off(self, s):
        # Use a fresh org so we can safely disable test_mode
        email = f"tmoff_{uuid.uuid4().hex[:8]}@example.com"
        data = _register_or_login(s, email, "Off2026!", "Off User", "Off Org")
        h = {"Authorization": f"Bearer {data['access_token']}"}
        # Turn off test_mode
        r0 = s.patch(f"{API}/settings/organization", headers=h, json={"test_mode": False})
        assert r0.status_code == 200
        r = s.post(f"{API}/campaigns", headers=h, json={
            "campaign_name": f"TEST_GPNoConfig_{uuid.uuid4().hex[:6]}",
            "industry": "Peintre", "country": "CH", "city": "Genève",
            "max_results": 2, "ai_analysis_enabled": False, "provider": "google_places",
        })
        assert r.status_code == 400
        assert "configur" in r.json().get("detail", "").lower()


# ------------- CSV import -------------
class TestCSVImport:
    def test_import_csv_success(self, s, demo_h):
        csv_body = (
            "company_name,industry,city,email,website\n"
            "TEST_CSV_Alpha,Electricien,Lausanne,info@alpha.ch,https://alpha.ch\n"
            "TEST_CSV_Beta,Peintre,Genève,,\n"
        )
        files = {"file": ("import.csv", csv_body, "text/csv")}
        r = requests.post(f"{API}/prospects/import-csv", headers=demo_h, files=files)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 2
        # Verify persistence with scoring
        prospects = s.get(f"{API}/prospects?q=TEST_CSV_Alpha", headers=demo_h).json()
        assert len(prospects) >= 1
        p = prospects[0]
        assert 0 <= p["qualification_score"] <= 100
        assert isinstance(p["qualification_reasons"], list)

    def test_import_csv_missing_header_400(self, s, demo_h):
        csv_body = "name,city\nFoo,Lausanne\n"
        files = {"file": ("bad.csv", csv_body, "text/csv")}
        r = requests.post(f"{API}/prospects/import-csv", headers=demo_h, files=files)
        assert r.status_code == 400


# ------------- Kill switch -------------
class TestKillSwitch:
    def _prepare_message(self, s, headers):
        r = s.post(f"{API}/campaigns", headers=headers, json={
            "campaign_name": f"TEST_KS_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien", "country": "CH", "city": "Lausanne",
            "max_results": 2, "ai_analysis_enabled": False,
        })
        cid = r.json()["campaign"]["id"]
        p = s.get(f"{API}/prospects?campaign_id={cid}", headers=headers).json()[0]
        gen = s.post(f"{API}/messages/generate", headers=headers,
                     json={"prospect_id": p["id"], "channel": "email"}).json()
        return gen["id"]

    def test_kill_switch_blocks_patch_status_sent(self, s, demo_h):
        mid = self._prepare_message(s, demo_h)
        s.post(f"{API}/security/kill-switch", headers=demo_h, json={"active": True})
        r = s.patch(f"{API}/messages/{mid}", headers=demo_h, json={"status": "sent"})
        assert r.status_code == 403
        # Also POST send
        r2 = s.post(f"{API}/messages/{mid}/send", headers=demo_h)
        assert r2.status_code == 403
        # cleanup
        s.post(f"{API}/security/kill-switch", headers=demo_h, json={"active": False})


# ------------- Test-mode audit + integrations status + structured logs -------------
class TestAuditAndIntegrations:
    def test_test_mode_off_creates_audit(self, s):
        email = f"audit_{uuid.uuid4().hex[:8]}@example.com"
        data = _register_or_login(s, email, "Aud2026!", "Aud", "AudOrg")
        h = {"Authorization": f"Bearer {data['access_token']}"}
        # Turn OFF
        r = s.patch(f"{API}/settings/organization", headers=h, json={"test_mode": False})
        assert r.status_code == 200
        acts = s.get(f"{API}/activities", headers=h).json()
        assert any(a.get("action_type") == "security.test_mode_off" for a in acts)

    def test_integration_connected_without_config_rejected(self, s, demo_h):
        # Reset any prior state to "not_configured"
        s.patch(f"{API}/integrations/custom_api", headers=demo_h,
                json={"connected": False, "config": {}, "status": "not_configured"})
        r = s.patch(f"{API}/integrations/custom_api", headers=demo_h,
                    json={"connected": True})
        assert r.status_code == 200
        d = r.json()
        assert d["connected"] is False
        assert d["status"] == "not_configured"

    def test_integration_secrets_redacted(self, s, demo_h):
        r = s.patch(f"{API}/integrations/openai", headers=demo_h, json={
            "connected": True,
            "status": "connected",
            "config": {"api_key": "sk-superSecret", "extra": "kept"},
        })
        assert r.status_code == 200
        cfg = r.json()["config"]
        assert cfg["api_key"] == "***"
        assert cfg["extra"] == "kept"

    def test_campaign_activity_has_structured_fields(self, s, demo_h):
        s.post(f"{API}/campaigns", headers=demo_h, json={
            "campaign_name": f"TEST_Audit_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien", "country": "CH", "city": "Lausanne",
            "max_results": 2, "ai_analysis_enabled": False,
        })
        acts = s.get(f"{API}/activities", headers=demo_h).json()
        camp_created = [a for a in acts if a.get("action_type") == "campaign.created"]
        assert camp_created, "expected campaign.created activity"
        a = camp_created[0]
        assert a.get("entity_type") == "campaign"
        assert a.get("entity_id")

    def test_kill_switch_toggle_activity_has_action_type(self, s, demo_h):
        s.post(f"{API}/security/kill-switch", headers=demo_h, json={"active": True})
        s.post(f"{API}/security/kill-switch", headers=demo_h, json={"active": False})
        acts = s.get(f"{API}/activities", headers=demo_h).json()
        assert any(a.get("action_type") == "security.kill_switch_toggled" for a in acts)


# ------------- Demo -------------
class TestDemoV2:
    def test_demo_has_reasons(self, s, demo_h):
        s.post(f"{API}/demo/seed", headers=demo_h)
        prospects = s.get(f"{API}/prospects", headers=demo_h).json()
        demos = [p for p in prospects if p.get("is_demo")]
        assert len(demos) >= 8
        for p in demos[:3]:
            assert p.get("qualification_score") is not None
            assert isinstance(p.get("qualification_reasons"), list) and len(p["qualification_reasons"]) > 0
        r = s.delete(f"{API}/demo/clear", headers=demo_h)
        assert r.status_code == 200


# ------------- Last login -------------
class TestLastLogin:
    def test_login_updates_last_login(self, s, demo_h):
        email = f"ll_{uuid.uuid4().hex[:8]}@example.com"
        data = _register_or_login(s, email, "LL2026!", "LL", "LLOrg")
        uid = data["user"]["id"]
        # Fetch user via admin (superadmin exposes last_login_at)
        users = s.get(f"{API}/admin/users", headers=demo_h).json()
        before = next((u for u in users if u["id"] == uid), {}).get("last_login_at")
        # login again
        r = s.post(f"{API}/auth/login", json={"email": email, "password": "LL2026!"})
        assert r.status_code == 200
        users2 = s.get(f"{API}/admin/users", headers=demo_h).json()
        after = next((u for u in users2 if u["id"] == uid), {}).get("last_login_at")
        assert after is not None
        if before is not None:
            assert after >= before
