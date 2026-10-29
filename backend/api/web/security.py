"""Host/Origin checks, individual sessions, CSRF and bounded login throttling."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from secrets import token_hex

from fastapi import Request, Response

from .. import config
from ..errors import require
from ..validation import public_user

SESSION_SECONDS = 43200
IDLE_SECONDS = 1800
csrf_token = token_hex(32)
# Single backend worker: session hashes only, never plaintext credentials.
sessions: dict[str, dict] = {}
login_attempts: dict[str, dict] = {}
auth_lock = threading.Lock()


def secure_cookies():
    return os.environ.get("HAEDAP_HTTPS", "").lower() in ("1", "true")


def check_login_limit(request, username):
    now = time.time()
    remote = request.client.host if request.client else "local"
    keys = [(digest("account:" + str(username).casefold()), 5), (digest("remote:" + remote), 100)]
    with auth_lock:
        for key in list(login_attempts):
            if login_attempts[key]["until"] <= now:
                del login_attempts[key]
        require(len(login_attempts) < 10000, "잠시 후 다시 로그인해 주세요.", "LOGIN_LIMIT", 429)
        for key, limit in keys:
            attempts = login_attempts.get(key, {"count": 0, "until": now + 900})
            require(attempts["count"] < limit, "로그인 시도가 많습니다. 15분 뒤 다시 시도하세요.", "LOGIN_LIMIT", 429)
        for key, _ in keys:
            attempts = login_attempts.setdefault(key, {"count": 0, "until": now + 900})
            attempts["count"] += 1


def clear_login_failures(username):
    with auth_lock:
        login_attempts.pop(digest("account:" + str(username).casefold()), None)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def guest_identity(request: Request, response: Response) -> dict:
    cookie = request.cookies.get("haedap_guest")
    if not cookie or not re.fullmatch(r"[a-f0-9]{64}", cookie):
        cookie = token_hex(32)
        response.set_cookie("haedap_guest", cookie, max_age=31536000, httponly=True,
                            samesite="strict", secure=secure_cookies())
    guest_id = "guest_" + digest(cookie)
    return {"id": guest_id, "username": "", "name": "일반 사용자 · " + guest_id[6:14],
            "role": "guest", "active": True, "version": 1}


def current_user(db, request: Request, guest: dict) -> dict:
    cookie = request.cookies.get("haedap_session")
    if not cookie:
        return guest
    session = sessions.get(digest(cookie))
    now = time.time()
    if not session or session["expires"] <= now or session.get("last_seen", now) + IDLE_SECONDS <= now:
        sessions.pop(digest(cookie), None)
        return guest
    user = db.user_by_id(session["id"])
    if not user or not user.get("active") or user["role"] not in ("admin", "operator", "viewer") or user["version"] != session["version"]:
        sessions.pop(digest(cookie), None)
        return guest
    session["last_seen"] = now
    return public_user(user)


def start_session(response: Response, user: dict) -> None:
    token = token_hex(32)
    now = time.time()
    with auth_lock:
        for key, session in list(sessions.items()):
            if session["expires"] <= now or session.get("last_seen", now) + IDLE_SECONDS <= now:
                sessions.pop(key, None)
        sessions[digest(token)] = {"id": user["id"], "version": user["version"],
                                  "expires": now + SESSION_SECONDS, "last_seen": now}
    response.set_cookie("haedap_session", token, max_age=SESSION_SECONDS, httponly=True,
                        samesite="strict", secure=secure_cookies())


def end_session(request: Request) -> None:
    cookie = request.cookies.get("haedap_session")
    if cookie:
        sessions.pop(digest(cookie), None)


def validate_origin(request: Request) -> None:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    match = re.fullmatch(r"([A-Za-z0-9.-]+)(?::\d+)?", host)
    require(bool(match and match.group(1).lower() in config.allowed_hosts()),
            "접속 주소를 확인해 주세요.", "HOST_DENIED", 403)
    origin = request.headers.get("origin")
    scheme = "https://" if secure_cookies() else "http://"
    require(not origin or origin == scheme + host, "동일 출처 요청만 허용합니다.", "ORIGIN_DENIED", 403)
    require(request.headers.get("sec-fetch-site") not in ("cross-site", "same-site"),
            "동일 출처 요청만 허용합니다.", "ORIGIN_DENIED", 403)


def authenticate_request(db, request: Request, response: Response) -> tuple[dict, dict]:
    validate_origin(request)
    guest = guest_identity(request, response)
    user = current_user(db, request, guest)
    identity = request.headers.get("x-haedap-identity")
    if request.url.path != "/api/health" and not request.url.path.startswith("/api/auth/") and identity:
        require(identity == user["id"], "사용자 상태가 바뀌었습니다.", "AUTH_REQUIRED", 401)
    return user, guest
