"""Comprehensive backend tests for Aura Hub API."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prospect-ai-hub-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@aurahub.io"
DEMO_PASSWORD = "Aura2026!"


# ------------- Fixtures -------------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _register_or_login(session, email, password, full_name="Test User", org_name="Test Org"):
    r = session.post(f"{API}/auth/register", json={
        "email": email, "password": password,
        "full_name": full_name, "organization_name": org_name,
    })
    if r.status_code == 200:
        return r.json()
    # try login
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def demo_auth(session):
    data = _register_or_login(session, DEMO_EMAIL, DEMO_PASSWORD, "Demo User", "Aura Demo SA")
    return data


@pytest.fixture(scope="session")
def demo_token(demo_auth):
    return demo_auth["access_token"]


@pytest.fixture(scope="session")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def second_auth(session):
    email = f"tenant2_{uuid.uuid4().hex[:8]}@example.com"
    data = _register_or_login(session, email, "Second2026!", "Second User", "Second Org SA")
    return data


@pytest.fixture(scope="session")
def second_headers(second_auth):
    return {"Authorization": f"Bearer {second_auth['access_token']}", "Content-Type": "application/json"}


# ------------- Health -------------
def test_health(session):
    r = session.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ------------- Auth -------------
class TestAuth:
    def test_register_new_user_seeds_defaults(self, session):
        email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(f"{API}/auth/register", json={
            "email": email, "password": "Passw0rd!",
            "full_name": "New User", "organization_name": "NewOrg"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "access_token" in d and d["user"]["email"] == email
        assert d["user"]["role"] == "owner"

        headers = {"Authorization": f"Bearer {d['access_token']}"}
        agents = session.get(f"{API}/agents", headers=headers).json()
        assert len(agents) == 6
        keys = {a["key"] for a in agents}
        assert "prospect_ai" in keys
        # security + ai settings seeded
        assert session.get(f"{API}/security", headers=headers).status_code == 200
        assert session.get(f"{API}/settings/ai", headers=headers).status_code == 200

    def test_register_duplicate_fails(self, session, demo_auth):
        r = session.post(f"{API}/auth/register", json={
            "email": DEMO_EMAIL, "password": DEMO_PASSWORD,
            "full_name": "x", "organization_name": "y"
        })
        assert r.status_code == 400

    def test_login_demo(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_bad_password(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me_requires_token(self, session):
        r = session.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_returns_user(self, session, demo_headers):
        r = session.get(f"{API}/auth/me", headers=demo_headers)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL

    def test_invalid_token_401(self, session):
        r = session.get(f"{API}/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401


# ------------- Agents -------------
class TestAgents:
    def test_list_agents(self, session, demo_headers):
        r = session.get(f"{API}/agents", headers=demo_headers)
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) == 6
        pa = next(a for a in agents if a["key"] == "prospect_ai")
        assert pa["status"] == "available"

    def test_patch_agent(self, session, demo_headers):
        r = session.patch(f"{API}/agents/prospect_ai",
                          headers=demo_headers, json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["enabled"] is True

    def test_patch_unknown_agent_404(self, session, demo_headers):
        r = session.patch(f"{API}/agents/nonexistent_agent",
                          headers=demo_headers, json={"enabled": True})
        assert r.status_code == 404


# ------------- Campaigns / Prospects -------------
class TestCampaignsAndProspects:
    @pytest.fixture(scope="class")
    def created_campaign(self, session, demo_headers):
        payload = {
            "campaign_name": f"TEST_Campaign_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien",
            "country": "CH",
            "city": "Lausanne",
            "max_results": 5,
            "ai_analysis_enabled": True,
            "service_to_sell": ["IA de réponse client"],
        }
        r = session.post(f"{API}/campaigns", headers=demo_headers, json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["prospects_count"] > 0
        assert "campaign" in d
        return d

    def test_create_and_analyze(self, created_campaign):
        camp = created_campaign["campaign"]
        assert camp["stats"]["prospects_found"] > 0

    def test_prospects_have_analysis(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        r = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers)
        assert r.status_code == 200
        prospects = r.json()
        assert len(prospects) > 0
        p = prospects[0]
        assert p.get("ai_analysis") is not None
        score = p["ai_analysis"]["ai_opportunity_score"]
        assert 0 <= score <= 100

    def test_list_campaigns_org_scoped(self, session, demo_headers):
        r = session.get(f"{API}/campaigns", headers=demo_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_single_prospect(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        pid = prospects[0]["id"]
        r = session.get(f"{API}/prospects/{pid}", headers=demo_headers)
        assert r.status_code == 200
        assert r.json()["id"] == pid

    def test_prospect_filters(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        r = session.get(f"{API}/prospects?campaign_id={camp_id}&min_score=0", headers=demo_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1
        r2 = session.get(f"{API}/prospects?q=xyzzz_nomatch_zzz", headers=demo_headers)
        assert r2.status_code == 200
        assert r2.json() == []

    def test_patch_prospect(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        pid = prospects[0]["id"]
        r = session.patch(f"{API}/prospects/{pid}", headers=demo_headers, json={"status": "to_contact"})
        assert r.status_code == 200
        assert r.json()["status"] == "to_contact"

    def test_add_note(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        pid = prospects[0]["id"]
        r = session.post(f"{API}/prospects/{pid}/notes", headers=demo_headers, json={"text": "Hello"})
        assert r.status_code == 200
        assert r.json()["text"] == "Hello"
        # Persistence check
        p = session.get(f"{API}/prospects/{pid}", headers=demo_headers).json()
        assert any(n["text"] == "Hello" for n in p["notes"])

    def test_bulk_set_status(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        ids = [p["id"] for p in prospects[:2]]
        r = session.post(f"{API}/prospects/bulk", headers=demo_headers,
                         json={"action": "set_status", "ids": ids, "status": "validated"})
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_bulk_delete(self, session, demo_headers, created_campaign):
        camp_id = created_campaign["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        # delete the last one
        if len(prospects) < 2:
            pytest.skip("not enough prospects")
        target_id = prospects[-1]["id"]
        r = session.post(f"{API}/prospects/bulk", headers=demo_headers,
                         json={"action": "delete", "ids": [target_id]})
        assert r.status_code == 200
        # Verify deletion
        g = session.get(f"{API}/prospects/{target_id}", headers=demo_headers)
        assert g.status_code == 404


# ------------- Messages -------------
class TestMessages:
    @pytest.fixture(scope="class")
    def prospect_id(self, session, demo_headers):
        # Create a small campaign to have a fresh prospect
        payload = {
            "campaign_name": f"TEST_Msg_{uuid.uuid4().hex[:6]}",
            "industry": "Peintre", "country": "CH", "city": "Genève",
            "max_results": 3, "ai_analysis_enabled": True,
        }
        r = session.post(f"{API}/campaigns", headers=demo_headers, json=payload)
        assert r.status_code == 200
        camp_id = r.json()["campaign"]["id"]
        prospects = session.get(f"{API}/prospects?campaign_id={camp_id}", headers=demo_headers).json()
        return prospects[0]["id"]

    def test_generate_message(self, session, demo_headers, prospect_id):
        r = session.post(f"{API}/messages/generate", headers=demo_headers,
                         json={"prospect_id": prospect_id, "channel": "email"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "draft"
        assert d["body"]
        # prospect should be message_ready
        p = session.get(f"{API}/prospects/{prospect_id}", headers=demo_headers).json()
        assert p["status"] == "message_ready"

    def test_list_messages_scoped(self, session, demo_headers, prospect_id):
        r = session.get(f"{API}/messages?prospect_id={prospect_id}", headers=demo_headers)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 1
        assert all(m["prospect_id"] == prospect_id for m in msgs)

    def test_patch_message(self, session, demo_headers, prospect_id):
        msgs = session.get(f"{API}/messages?prospect_id={prospect_id}", headers=demo_headers).json()
        mid = msgs[0]["id"]
        r = session.patch(f"{API}/messages/{mid}", headers=demo_headers,
                         json={"subject": "Updated subject"})
        assert r.status_code == 200
        assert r.json()["subject"] == "Updated subject"

    def test_send_in_test_mode(self, session, demo_headers, prospect_id):
        # ensure kill switch off
        session.post(f"{API}/security/kill-switch", headers=demo_headers, json={"active": False})
        msgs = session.get(f"{API}/messages?prospect_id={prospect_id}", headers=demo_headers).json()
        mid = msgs[0]["id"]
        r = session.post(f"{API}/messages/{mid}/send", headers=demo_headers)
        assert r.status_code == 200
        assert r.json()["test_mode"] is True
        # verify message status = test
        msg_after = [m for m in session.get(f"{API}/messages?prospect_id={prospect_id}",
                     headers=demo_headers).json() if m["id"] == mid][0]
        assert msg_after["status"] == "test"

    def test_kill_switch_blocks_send(self, session, demo_headers, prospect_id):
        session.post(f"{API}/security/kill-switch", headers=demo_headers, json={"active": True})
        # Generate a fresh msg
        gen = session.post(f"{API}/messages/generate", headers=demo_headers,
                            json={"prospect_id": prospect_id, "channel": "email"}).json()
        r = session.post(f"{API}/messages/{gen['id']}/send", headers=demo_headers)
        assert r.status_code == 403
        # Turn off for cleanup
        session.post(f"{API}/security/kill-switch", headers=demo_headers, json={"active": False})


# ------------- Security / Integrations / Settings -------------
class TestMisc:
    def test_get_security(self, session, demo_headers):
        r = session.get(f"{API}/security", headers=demo_headers)
        assert r.status_code == 200
        assert "kill_switch_active" in r.json()

    def test_patch_security(self, session, demo_headers):
        r = session.patch(f"{API}/security", headers=demo_headers,
                         json={"daily_sending_limit": 42})
        assert r.status_code == 200
        assert r.json()["daily_sending_limit"] == 42

    def test_integrations_default_list(self, session, demo_headers):
        r = session.get(f"{API}/integrations", headers=demo_headers)
        assert r.status_code == 200
        keys = {i["key"] for i in r.json()}
        assert "openai" in keys and "gmail" in keys

    def test_integration_toggle_persists(self, session, demo_headers):
        r = session.patch(f"{API}/integrations/openai", headers=demo_headers,
                         json={"connected": True})
        assert r.status_code == 200
        assert r.json()["connected"] is True
        # persistence
        openai_row = [i for i in session.get(f"{API}/integrations", headers=demo_headers).json()
                       if i["key"] == "openai"][0]
        assert openai_row["connected"] is True

    def test_ai_settings(self, session, demo_headers):
        r = session.get(f"{API}/settings/ai", headers=demo_headers)
        assert r.status_code == 200
        r2 = session.patch(f"{API}/settings/ai", headers=demo_headers, json={"creativity": 0.7})
        assert r2.status_code == 200
        assert r2.json()["creativity"] == 0.7

    def test_org_settings(self, session, demo_headers):
        r = session.get(f"{API}/settings/organization", headers=demo_headers)
        assert r.status_code == 200
        assert "test_mode" in r.json()
        r2 = session.patch(f"{API}/settings/organization", headers=demo_headers, json={"test_mode": True})
        assert r2.status_code == 200
        assert r2.json()["test_mode"] is True

    def test_analytics_overview(self, session, demo_headers):
        r = session.get(f"{API}/analytics/overview", headers=demo_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ("kpis", "by_city", "by_industry", "by_status", "by_day"):
            assert k in d
        assert "prospects_found" in d["kpis"]

    def test_activities_sorted_desc(self, session, demo_headers):
        r = session.get(f"{API}/activities", headers=demo_headers)
        assert r.status_code == 200
        acts = r.json()
        assert len(acts) > 0
        # Check sort order
        for i in range(len(acts) - 1):
            assert acts[i]["created_at"] >= acts[i+1]["created_at"]


# ------------- Demo seed/clear -------------
class TestDemo:
    def test_demo_seed_and_clear(self, session, demo_headers):
        r = session.post(f"{API}/demo/seed", headers=demo_headers)
        assert r.status_code == 200
        assert r.json()["prospects"] == 8
        # verify demo prospects present
        prospects = session.get(f"{API}/prospects", headers=demo_headers).json()
        demos = [p for p in prospects if p.get("is_demo")]
        assert len(demos) >= 8
        # Clear
        r2 = session.delete(f"{API}/demo/clear", headers=demo_headers)
        assert r2.status_code == 200
        assert r2.json()["prospects_deleted"] >= 8


# ------------- Multi-tenant isolation -------------
class TestMultiTenantIsolation:
    def test_second_org_cannot_see_first_org_data(self, session, demo_headers, second_headers):
        # First org creates a campaign
        payload = {
            "campaign_name": f"TEST_Iso_{uuid.uuid4().hex[:6]}",
            "industry": "Electricien", "country": "CH", "city": "Lausanne",
            "max_results": 3, "ai_analysis_enabled": True,
        }
        r = session.post(f"{API}/campaigns", headers=demo_headers, json=payload)
        assert r.status_code == 200
        first_camp_id = r.json()["campaign"]["id"]

        # Second org lists campaigns and prospects — must not see first org's data
        s_campaigns = session.get(f"{API}/campaigns", headers=second_headers).json()
        assert all(c["id"] != first_camp_id for c in s_campaigns)

        s_prospects = session.get(f"{API}/prospects?campaign_id={first_camp_id}", headers=second_headers).json()
        assert s_prospects == []

        # Second org tries to GET a first-org prospect directly
        first_prospects = session.get(f"{API}/prospects?campaign_id={first_camp_id}", headers=demo_headers).json()
        if first_prospects:
            pid = first_prospects[0]["id"]
            r_iso = session.get(f"{API}/prospects/{pid}", headers=second_headers)
            assert r_iso.status_code == 404

        # Second org's activities should not include first org's activities
        s_acts = session.get(f"{API}/activities", headers=second_headers).json()
        # they are new, likely empty or few; just check no reference to first-org campaign name
        assert not any(payload["campaign_name"] in (a.get("target") or "") for a in s_acts)
