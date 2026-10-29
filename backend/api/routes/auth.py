"""Individual crew, viewer and administrator login and password rotation."""

from __future__ import annotations

import logging

from ..errors import ApiError
from ..web import security


def setup(_ctx):
    raise ApiError(410, "SETUP_DISABLED", "초기 설정은 필요하지 않습니다.")


def login(ctx):
    request, body = ctx.request, ctx.body
    username = body.get("username", "")
    try:
        security.check_login_limit(request, username)
        admin = ctx.db.authenticate(username, body.get("password", ""))
    except ApiError as exc:
        # Failed request transactions roll back. Operational logs retain the event
        # without passwords, raw usernames, cookies or submitted request bodies.
        logging.getLogger("haedap.auth").warning(
            "Login rejected account=%s remote=%s code=%s",
            security.digest(str(username)), request.client.host if request.client else "local", exc.code)
        raise
    security.clear_login_failures(username)
    security.end_session(request)
    security.start_session(ctx.response, admin)
    return {"user": admin}


def logout(ctx):
    security.end_session(ctx.request)
    ctx.response.delete_cookie("haedap_session")
    if ctx.user["role"] != "guest":
        ctx.db.audit(ctx.user, "auth", "로그아웃", ctx.user["username"])
    return {"ok": True, "user": ctx.guest}


def password(ctx):
    security.check_login_limit(ctx.request, ctx.user["username"])
    user = ctx.db.change_password(ctx.user, ctx.body)
    security.clear_login_failures(ctx.user["username"])
    security.end_session(ctx.request)
    security.start_session(ctx.response, user)
    return {"user": user}


POST = {"auth/setup": setup, "auth/login": login, "auth/logout": logout, "auth/password": password}
