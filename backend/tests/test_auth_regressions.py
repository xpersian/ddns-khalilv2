"""Regression tests for authentication, pagination and backup defects.

Covers:
- Email addresses are case-insensitive (login, duplicate registration).
- Accounts without a password (Google/OAuth-only) return 401/400 rather
  than crashing bcrypt with "Invalid salt".
- Activity-log pagination rejects out-of-range pages instead of passing a
  negative skip to MongoDB.
- Backup settings and the bot test endpoint tolerate null/invalid input
  instead of raising AttributeError/ValueError as a 500.

Run against a live backend:
    REACT_APP_BACKEND_URL=http://127.0.0.1:8001 pytest backend/tests/test_auth_regressions.py
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123456")
PASSWORD = "password1234"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.trust_env = False  # ignore any HTTP(S)_PROXY pointing away from localhost
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_headers(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in admin login response: {r.json()}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def new_user(session):
    """Register a fresh user using a MIXED-CASE email address."""
    stamp = int(time.time() * 1000)
    mixed = f"CaseUser{stamp}@Gmail.com"
    r = session.post(f"{API}/auth/register", json={
        "email": mixed, "password": PASSWORD, "name": "Case User"})
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    return {"mixed": mixed, "lower": mixed.lower(), "body": r.json()}


class TestEmailCaseInsensitivity:
    def test_email_is_stored_lowercased(self, new_user):
        assert new_user["body"]["user"]["email"] == new_user["lower"]

    def test_login_with_lowercase_email(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["lower"], "password": PASSWORD})
        assert r.status_code == 200, f"Lowercase login rejected: {r.status_code} {r.text}"

    def test_login_with_original_mixed_case_email(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["mixed"], "password": PASSWORD})
        assert r.status_code == 200, f"Mixed-case login rejected: {r.status_code} {r.text}"

    def test_login_with_uppercase_email(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["mixed"].upper(), "password": PASSWORD})
        assert r.status_code == 200, f"Uppercase login rejected: {r.status_code} {r.text}"

    def test_surrounding_whitespace_is_ignored(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": f'  {new_user["lower"]}  ', "password": PASSWORD})
        assert r.status_code == 200, f"Padded login rejected: {r.status_code} {r.text}"

    def test_duplicate_registration_differing_only_by_case_is_rejected(self, session, new_user):
        r = session.post(f"{API}/auth/register", json={
            "email": new_user["mixed"].upper(), "password": PASSWORD, "name": "Dupe"})
        assert r.status_code == 400, f"Case-variant duplicate was accepted: {r.status_code} {r.text}"
        assert "already registered" in r.json().get("detail", "").lower()

    def test_wrong_password_still_rejected(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["lower"], "password": "definitely-wrong"})
        assert r.status_code == 401


class TestPasswordlessAccounts:
    """Google/OAuth-only accounts have an empty password_hash. bcrypt raises
    ValueError('Invalid salt') on those, which surfaced as HTTP 500."""

    @pytest.fixture
    def oauth_user(self):
        pytest.importorskip("pymongo")
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
        db_name = os.environ.get("DB_NAME", "ddns_test")
        stamp = int(time.time() * 1000)
        email = f"oauthonly{stamp}@gmail.com"
        db = MongoClient(mongo_url)[db_name]
        db.users.insert_one({
            "id": f"oauth-{stamp}", "email": email, "name": "OAuth User",
            "password_hash": "", "google_id": f"sub-{stamp}", "plan": "free",
            "role": "user", "record_count": 0, "record_limit": 2,
            "referral_code": f"oauth{stamp % 100000}", "referred_by": None,
            "referral_count": 0, "referral_bonus": 0, "email_verified": True,
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        yield email
        db.users.delete_one({"id": f"oauth-{stamp}"})

    def test_login_returns_401_not_500(self, session, oauth_user):
        r = session.post(f"{API}/auth/login", json={
            "email": oauth_user, "password": "anything"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_empty_password_returns_401_not_500(self, session, oauth_user):
        r = session.post(f"{API}/auth/login", json={"email": oauth_user, "password": ""})
        assert r.status_code in (401, 422), f"Expected 401/422, got {r.status_code}: {r.text}"


class TestActivityLogPagination:
    """page < 1 produced a negative skip, which pymongo rejects outright."""

    @pytest.fixture
    def user_headers(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["lower"], "password": PASSWORD})
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}

    @pytest.mark.parametrize("page", [0, -1, -1000])
    def test_user_logs_out_of_range_page(self, session, user_headers, page):
        r = session.get(f"{API}/activity/logs?page={page}&limit=20", headers=user_headers)
        assert r.status_code == 200, f"page={page} -> {r.status_code}: {r.text}"
        assert r.json()["page"] >= 1

    @pytest.mark.parametrize("page", [0, -7])
    def test_admin_logs_out_of_range_page(self, session, admin_headers, page):
        r = session.get(f"{API}/admin/activity/logs?page={page}&limit=50", headers=admin_headers)
        assert r.status_code == 200, f"page={page} -> {r.status_code}: {r.text}"

    @pytest.mark.parametrize("limit", [0, -5, 10 ** 6])
    def test_out_of_range_limit_is_clamped(self, session, user_headers, limit):
        r = session.get(f"{API}/activity/logs?page=1&limit={limit}", headers=user_headers)
        assert r.status_code == 200, f"limit={limit} -> {r.status_code}: {r.text}"
        assert len(r.json()["logs"]) <= 200


class TestBackupSettingsInputHandling:
    """The admin form sends null for fields the operator left untouched.
    str.strip()/int() on None raised, surfacing as HTTP 500."""

    @pytest.mark.parametrize("field", ["bot_token", "admin_id"])
    def test_null_string_field_is_accepted(self, session, admin_headers, field):
        r = session.put(f"{API}/admin/backup/settings", json={field: None}, headers=admin_headers)
        assert r.status_code == 200, f"{field}=null -> {r.status_code}: {r.text}"

    @pytest.mark.parametrize("value", [None, "abc", "", []])
    def test_non_numeric_interval_is_rejected_cleanly(self, session, admin_headers, value):
        r = session.put(f"{API}/admin/backup/settings",
                        json={"interval_minutes": value}, headers=admin_headers)
        assert r.status_code == 400, f"interval={value!r} -> {r.status_code}: {r.text}"

    @pytest.mark.parametrize("value,expected", [(0, 1), (-10, 1), (999999, 10080)])
    def test_interval_is_clamped(self, session, admin_headers, value, expected):
        r = session.put(f"{API}/admin/backup/settings",
                        json={"interval_minutes": value}, headers=admin_headers)
        assert r.status_code == 200, r.text
        got = session.get(f"{API}/admin/backup/settings", headers=admin_headers)
        assert got.json()["interval_minutes"] == expected

    def test_empty_body_is_accepted(self, session, admin_headers):
        r = session.put(f"{API}/admin/backup/settings", json={}, headers=admin_headers)
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("body", [
        {"bot_token": None, "admin_id": "1"},
        {"bot_token": "x", "admin_id": None},
        {},
    ])
    def test_test_bot_handles_missing_fields(self, session, admin_headers, body):
        r = session.post(f"{API}/admin/backup/test-bot", json=body, headers=admin_headers)
        assert r.status_code == 200, f"{body} -> {r.status_code}: {r.text}"
        assert r.json()["success"] is False

    def test_backup_settings_requires_admin(self, session):
        assert session.get(f"{API}/admin/backup/settings").status_code in (401, 403)
        assert session.post(f"{API}/admin/backup/now").status_code in (401, 403)
        assert session.post(f"{API}/admin/backup/restore").status_code in (401, 403)
