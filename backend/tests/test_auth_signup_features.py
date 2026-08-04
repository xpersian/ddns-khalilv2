"""
Backend tests for new auth features:
- /auth/signup-status (public)
- /auth/password-reset-status (public)
- /auth/forgot-password (SMTP gate -> 503)
- /auth/reset-password (SMTP gate -> 503)
- /admin/auth/signup-status (admin)
- /admin/auth/toggle-email-signup (admin)
- /auth/register gated by email_signup_enabled flag
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://farsi-feature-bug.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123456"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in admin login: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def ensure_signup_enabled_after_tests(session, admin_headers):
    """Make sure signup is enabled at start AND restored after tests."""
    session.put(f"{API}/admin/auth/toggle-email-signup", json={"enabled": True}, headers=admin_headers)
    yield
    session.put(f"{API}/admin/auth/toggle-email-signup", json={"enabled": True}, headers=admin_headers)


# Public endpoints
class TestPublicAuthFlags:
    def test_signup_status_public(self, session):
        r = session.get(f"{API}/auth/signup-status")
        assert r.status_code == 200
        data = r.json()
        assert "email_signup_enabled" in data
        assert isinstance(data["email_signup_enabled"], bool)
        # Default: should be True
        assert data["email_signup_enabled"] is True

    def test_password_reset_status_smtp_disabled(self, session):
        r = session.get(f"{API}/auth/password-reset-status")
        assert r.status_code == 200
        data = r.json()
        assert "enabled" in data
        # SMTP not configured in this env
        assert data["enabled"] is False

    def test_forgot_password_smtp_disabled_returns_503(self, session):
        r = session.post(f"{API}/auth/forgot-password", json={"email": "anyone@example.com"})
        assert r.status_code == 503, f"Expected 503, got {r.status_code} - {r.text}"
        body = r.json()
        msg = (body.get("detail") or body.get("message") or "").lower()
        assert "unavailable" in msg or "currently unavailable" in msg, f"Unexpected message: {body}"

    def test_reset_password_smtp_disabled_returns_503(self, session):
        r = session.post(f"{API}/auth/reset-password", json={
            "email": "anyone@example.com",
            "code": "000000",
            "new_password": "newpass1234"
        })
        assert r.status_code == 503, f"Expected 503, got {r.status_code} - {r.text}"


# Admin endpoints
class TestAdminSignupToggle:
    def test_admin_get_signup_status(self, session, admin_headers):
        r = session.get(f"{API}/admin/auth/signup-status", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "email_signup_enabled" in data
        assert isinstance(data["email_signup_enabled"], bool)

    def test_admin_get_signup_status_unauthorized(self, session):
        r = session.get(f"{API}/admin/auth/signup-status")
        assert r.status_code in (401, 403)

    def test_admin_toggle_off_then_register_blocked(self, session, admin_headers):
        # Toggle off
        r = session.put(f"{API}/admin/auth/toggle-email-signup",
                        json={"enabled": False}, headers=admin_headers)
        assert r.status_code == 200, f"Toggle off failed: {r.text}"
        body = r.json()
        assert body.get("email_signup_enabled") is False
        assert body.get("success") is True

        # Verify public endpoint reflects
        rp = session.get(f"{API}/auth/signup-status")
        assert rp.status_code == 200
        assert rp.json()["email_signup_enabled"] is False

        # Try register -> 403
        unique_email = f"TEST_{int(time.time())}@example.com"
        rr = session.post(f"{API}/auth/register", json={
            "email": unique_email,
            "password": "password1234",
            "name": "Test User"
        })
        assert rr.status_code == 403, f"Expected 403 when signup disabled, got {rr.status_code} - {rr.text}"
        body_r = rr.json()
        msg = (body_r.get("detail") or body_r.get("message") or "").lower()
        assert "disabled" in msg or "currently disabled" in msg, f"Unexpected msg: {body_r}"

    def test_admin_toggle_on_then_register_works(self, session, admin_headers):
        # Toggle on
        r = session.put(f"{API}/admin/auth/toggle-email-signup",
                        json={"enabled": True}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json().get("email_signup_enabled") is True

        # Register a fresh user
        unique_email = f"test.signup.{int(time.time()*1000)}@gmail.com"
        rr = session.post(f"{API}/auth/register", json={
            "email": unique_email,
            "password": "password1234",
            "name": "Test SignupUser"
        })
        # Accept 200 or 201
        assert rr.status_code in (200, 201), f"Register failed after enabling: {rr.status_code} {rr.text}"
        # Cleanup not strictly needed but log
        print(f"Created test user {unique_email}")

    def test_admin_toggle_unauthorized(self, session):
        r = session.put(f"{API}/admin/auth/toggle-email-signup", json={"enabled": False})
        assert r.status_code in (401, 403)
