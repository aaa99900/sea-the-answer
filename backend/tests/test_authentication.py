"""Authentication boundaries and lifecycle; no external identity service required."""
from copy import deepcopy
import os
import time

import pytest
from fastapi.testclient import TestClient

from api import deps, main
from api.errors import ApiError
from api.passwords import hash_password, validate_password, verify_password
from api.web import security
from test_fastapi_api import ADMIN, FakeWorkspace
from rag_postgres_support import configure_api, isolated_workspace, login


@pytest.fixture
def auth(monkeypatch):
    accounts = {role: {**deepcopy(ADMIN), "id": role, "username": role, "role": role,
                       "must_change_password": False} for role in ("admin", "operator", "viewer")}

    class Accounts(FakeWorkspace):
        def user_by_id(self, user_id):
            return accounts.get(user_id)

        def authenticate(self, username, password):
            user = accounts.get(username)
            if not user or not user["active"] or password != "Test-only-password":
                raise ApiError(401, "LOGIN_FAILED", "잘못된 인증")
            return deepcopy(user)

    monkeypatch.setattr(deps, "Workspace", Accounts)
    monkeypatch.setattr(deps, "initialized", True)
    monkeypatch.setattr(security, "sessions", {})
    monkeypatch.setattr(security, "login_attempts", {})
    monkeypatch.delenv("HAEDAP_HTTPS", raising=False)
    client = TestClient(main.app, base_url="http://localhost:5173")
    headers = {"X-Haedap-Token": client.get("/api/health").json()["csrfToken"]}
    return client, headers, accounts


@pytest.mark.parametrize("method,path", [
    ("get", "documents"), ("get", "documents/secret/pdf"), ("get", "operations"),
    ("get", "reports"), ("get", "history"), ("get", "users"), ("get", "logs"),
    ("get", "backups"), ("get", "tools"), ("post", "ask"), ("post", "search"),
    ("post", "changes"), ("post", "reports"), ("post", "auth/password"),
])
def test_anonymous_cannot_call_business_api(auth, method, path):
    client, headers, _ = auth
    response = getattr(client, method)("/api/" + path, headers=headers,
                                      **({"json": {}} if method == "post" else {}))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_all_account_roles_can_login_and_logout(auth, role):
    client, headers, _ = auth
    response = client.post("/api/auth/login", headers=headers,
                           json={"username": role, "password": "Test-only-password", "role": "admin"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == role
    cookie = client.cookies.get("haedap_session")
    assert cookie and cookie not in security.sessions
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/health").json()["authenticated"] is True
    assert client.post("/api/auth/logout", headers=headers, json={}).status_code == 200
    assert security.digest(cookie) not in security.sessions
    assert client.get("/api/health").json()["authenticated"] is False


@pytest.mark.parametrize("change", ["version", "inactive", "idle", "expired"])
def test_sessions_are_revoked(auth, change):
    client, headers, accounts = auth
    client.post("/api/auth/login", headers=headers, json={"username": "operator", "password": "Test-only-password"})
    session = security.sessions[security.digest(client.cookies.get("haedap_session"))]
    if change == "version":
        accounts["operator"]["version"] += 1
    elif change == "inactive":
        accounts["operator"]["active"] = False
    elif change == "idle":
        session["last_seen"] = time.time() - security.IDLE_SECONDS - 1
    else:
        session["expires"] = time.time() - 1
    assert client.get("/api/health").json()["authenticated"] is False
    assert client.get("/api/documents").status_code == 401


def test_initial_password_cannot_access_business_data(auth):
    client, headers, accounts = auth
    accounts["operator"]["must_change_password"] = True
    client.post("/api/auth/login", headers=headers, json={"username": "operator", "password": "Test-only-password"})
    assert client.get("/api/health").json()["documents"] == 0
    response = client.get("/api/documents")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"


def test_account_login_limit_applies_across_client_addresses(auth):
    client, headers, _ = auth
    for _ in range(5):
        assert client.post("/api/auth/login", headers=headers,
                           json={"username": "operator", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", headers=headers,
                       json={"username": "operator", "password": "Test-only-password"}).status_code == 429
    assert client.post("/api/auth/login", headers=headers,
                       json={"username": "viewer", "password": "Test-only-password"}).status_code == 200


def test_https_cookies_and_origin(auth, monkeypatch):
    _, _, _ = auth
    monkeypatch.setenv("HAEDAP_HTTPS", "true")
    client = TestClient(main.app, base_url="https://localhost:5173")
    headers = {"X-Haedap-Token": client.get("/api/health").json()["csrfToken"], "Origin": "https://localhost:5173"}
    response = client.post("/api/auth/login", headers=headers,
                           json={"username": "admin", "password": "Test-only-password"})
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]
    assert client.get("/api/health").json()["authenticated"] is True
    headers["Origin"] = "http://localhost:5173"
    assert client.post("/api/auth/logout", headers=headers, json={}).status_code == 403


def test_passwords_preserve_unicode_and_whitespace_without_truncation():
    password = "선원 개인의 긴 비밀번호" * 5 + " "
    encoded = hash_password(validate_password(password))
    assert verify_password(password, encoded)
    assert not verify_password(password.rstrip(), encoded)
    assert not verify_password(password[:43], encoded)
    with pytest.raises(ApiError):
        validate_password("1234")
    with pytest.raises(ApiError):
        validate_password("a" * 129)


def test_real_database_account_lifecycle(monkeypatch):
    dsn = os.getenv("HAEDAP_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("HAEDAP_TEST_DATABASE_URL required")
    with isolated_workspace(dsn) as (store, request_workspace):
        configure_api(monkeypatch, request_workspace)
        admin = TestClient(main.app, base_url="http://localhost:5173")
        headers = login(admin)
        response = admin.post("/api/users", headers=headers, json={
            "username": "new-crew", "name": "선원", "role": "operator",
            "password": "Initial-only-password",
        })
        assert response.status_code == 200
        user = response.json()["user"]
        assert user["must_change_password"] and "password" not in user
        crew = TestClient(main.app, base_url="http://localhost:5173")
        crew_headers = login(crew, "new-crew", "Initial-only-password")
        assert crew.get("/api/documents").status_code == 403
        second = TestClient(main.app, base_url="http://localhost:5173")
        login(second, "new-crew", "Initial-only-password")
        changed = crew.post("/api/auth/password", headers=crew_headers, json={
            "currentPassword": "Initial-only-password", "newPassword": "Personal-only-password",
        })
        assert changed.status_code == 200
        assert not changed.json()["user"]["must_change_password"]
        assert crew.get("/api/documents").status_code == 200
        assert crew.get("/api/users").status_code == 403
        assert crew.get("/api/backups").status_code == 403
        assert second.get("/api/documents").status_code == 401
        report = crew.post("/api/reports", headers=crew_headers, json={
            "title": "Private crew draft", "type": "규정 검토", "text": "Private evidence notes",
            "sources": [], "version": 0,
        })
        assert report.status_code == 200
        report_id = report.json()["report"]["id"]
        other = TestClient(main.app, base_url="http://localhost:5173")
        other_headers = login(other, "crew")
        assert other.get(f"/api/reports/{report_id}").status_code == 404
        assert all(item["id"] != report_id for item in other.get("/api/reports").json()["reports"])
        assert other.post("/api/reports", headers=other_headers,
                          json={**report.json()["report"], "text": "Overwrite attempt"}).status_code == 403
        new_version = changed.json()["user"]["version"]
        # The original user's stale version cannot overwrite the password change.
        assert admin.post("/api/users", headers=headers, json={**user, "active": False}).status_code == 409
        assert admin.post("/api/users", headers=headers,
                          json={**user, "version": new_version, "active": False}).status_code == 200
        assert crew.get("/api/documents").status_code == 401
        owner = admin.get("/api/health").json()["user"]
        assert admin.post("/api/users", headers=headers, json={**owner, "role": "operator"}).status_code == 403
        events = store.all("SELECT detail FROM audit WHERE category='users'")
        assert any(event["detail"].get("userId") == user["id"] for event in events)
        assert "Personal-only-password" not in str(events)
