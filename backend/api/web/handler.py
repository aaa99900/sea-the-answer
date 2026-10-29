"""The single /api/{path} entry point: request slots, body limits, DB session, auth, CSRF, then dispatch."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from .. import deps
from ..errors import ApiError, require
from ..routes import RequestContext, dispatch
from . import security
from .concurrency import database_request_lock, release_request, reserve_request

router = APIRouter()

MB = 1024 * 1024
BODY_LIMITS = {"backups/import": 100 * MB, "changes": 38 * MB}
DEFAULT_BODY_LIMIT = 1 * MB


def handle(request: Request, response: Response, path: str, body: dict | None):
    with deps.open_workspace() as db:
        deps.initialize(db)
        database_request_lock(db, exclusive=path == "backups/restore" and request.method == "POST")
        user, guest = security.authenticate_request(db, request, response)
        if request.method == "POST":
            require(request.headers.get("x-haedap-token") == security.csrf_token,
                    "연결을 새로고침한 뒤 다시 시도하세요.", "SESSION_EXPIRED", 403)
            require(isinstance(body, dict), "JSON 객체가 필요합니다.")
        if path not in ("health", "auth/login", "auth/logout", "auth/setup"):
            require(user["role"] in ("admin", "operator", "viewer"),
                    "로그인 후 이용해 주세요.", "AUTH_REQUIRED", 401)
        if path not in ("health", "auth/login", "auth/logout", "auth/password", "auth/setup"):
            require(not user.get("must_change_password"), "비밀번호를 변경한 뒤 이용해 주세요.",
                    "PASSWORD_CHANGE_REQUIRED", 403)
        context = RequestContext(db=db, user=user, guest=guest, path=path, method=request.method,
                                 body=body or {}, request=request, response=response)
        result = dispatch(context)
        if user["role"] != "guest" and path not in ("health", "auth/login", "auth/logout", "auth/password", "backups/restore"):
            db.audit(user, "access", request.method, path,
                     {"remote": request.client.host if request.client else "local"})
        return result


@router.api_route("/api/{path:path}", methods=["GET", "POST"])
async def api(request: Request, response: Response, path: str):
    reserve_request(path)
    try:
        body = None
        if request.method == "POST":
            require(request.headers.get("content-type", "").split(";", 1)[0].strip() == "application/json",
                    "application/json 요청이 필요합니다.", "CONTENT_TYPE", 415)
            raw = await request.body()
            require(len(raw) <= BODY_LIMITS.get(path, DEFAULT_BODY_LIMIT), "요청이 너무 큽니다.", "BODY_TOO_LARGE", 413)
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ApiError(400, "INVALID_JSON", "올바른 JSON이 필요합니다.") from exc
        result = await run_in_threadpool(handle, request, response, path, body)
        if path == "backups/restore" and request.method == "POST":
            security.sessions.clear()
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return result
    finally:
        release_request(path)
