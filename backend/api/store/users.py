"""Accounts, login, permission checks and the audit log."""

from __future__ import annotations

import re
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..errors import require
from ..passwords import DUMMY_PASSWORD, hash_password, validate_password, verify_password
from ..validation import public_user, text, utc_now


class UserStore:
    def user_by_id(self, user_id: str) -> dict | None:
        return self.one("SELECT * FROM users WHERE id=%s AND active=true", (user_id,))

    def authenticate(self, username: str, password: str) -> dict:
        require(isinstance(username, str) and len(username) <= 40,
                "아이디 또는 비밀번호가 올바르지 않습니다.", "LOGIN_FAILED", 401)
        user = self.one("SELECT * FROM users WHERE username=%s AND active=true", (username,))
        valid = verify_password(password, user["password"] if user else DUMMY_PASSWORD)
        require(user and valid and user["role"] in ("admin", "operator", "viewer"),
                "아이디 또는 비밀번호가 올바르지 않습니다.", "LOGIN_FAILED", 401)
        self.audit(user, "auth", "로그인", username)
        return public_user(user)

    def audit(self, user: dict | None, category: str, action: str, target: str, detail=None) -> None:
        self.run("INSERT INTO audit VALUES(%s,%s,%s,%s,%s,%s,%s)",
                 (str(uuid4()), utc_now(), user.get("name", "시스템") if user else "시스템",
                  category, action, str(target), Jsonb({**(detail or {}), "actorId": user.get("id") if user else None})))

    def permit(self, user: dict, roles=("admin",)) -> None:
        require(user["role"] in roles, "이 작업을 수행할 권한이 없습니다.", "FORBIDDEN", 403)

    def save_user(self, actor: dict, payload: dict) -> dict:
        self.permit(actor)
        # Serialize account lifecycle changes, including concurrent last-admin removal.
        self.one("SELECT pg_advisory_xact_lock(72419302)")
        username = text(payload.get("username"), "아이디", 40)
        require(bool(re.fullmatch(r"[A-Za-z0-9._-]{3,40}", username)), "아이디는 영문·숫자·점·밑줄·하이픈 3~40자입니다.")
        require(payload.get("role") in ("admin", "operator", "viewer"), "권한을 확인해 주세요.")
        old = self.one("SELECT * FROM users WHERE id=%s FOR UPDATE", (payload["id"],)) if payload.get("id") else None
        if payload.get("id"):
            require(old and old["version"] == payload.get("version"), "사용자 정보가 변경되었습니다.", "VERSION_CONFLICT", 409)
        active = payload.get("active") is not False
        if old and old["role"] == "admin" and (not active or payload["role"] != "admin"):
            require(old["id"] != actor["id"], "본인의 관리자 권한은 다른 관리자가 변경해야 합니다.", "FORBIDDEN", 403)
            require(bool(self.one("SELECT 1 FROM users WHERE role='admin' AND active=true AND id<>%s", (old["id"],))),
                    "최소 한 명의 활성 관리자가 필요합니다.")
        password = old["password"] if old else None
        if payload.get("password"):
            password = hash_password(validate_password(payload["password"], username))
        require(password, "비밀번호를 입력해 주세요.")
        user_id = old["id"] if old else str(uuid4())
        require(not self.one("SELECT 1 FROM users WHERE username=%s AND id<>%s", (username, user_id)), "이미 사용 중인 아이디입니다.")
        must_change = bool(payload.get("password")) or not old or old["must_change_password"]
        self.run("""INSERT INTO users(id,username,name,role,password,active,version,must_change_password)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET username=excluded.username,name=excluded.name,
            role=excluded.role,password=excluded.password,active=excluded.active,version=excluded.version,
            must_change_password=excluded.must_change_password""",
            (user_id, username, text(payload.get("name"), "이름", 80), payload["role"],
             password, active, (old or {}).get("version", 0) + 1, must_change))
        self.audit(actor, "users", "사용자 변경" if old else "사용자 등록", username, {
            "userId": user_id,
            "before": {key: old[key] for key in ("role", "active")} if old else None,
            "after": {"role": payload["role"], "active": active},
            "passwordReset": bool(payload.get("password")),
        })
        return public_user(self.one("SELECT * FROM users WHERE id=%s", (user_id,)))

    def change_password(self, actor: dict, payload: dict) -> dict:
        self.permit(actor, ("admin", "operator", "viewer"))
        old = self.one("SELECT * FROM users WHERE id=%s FOR UPDATE", (actor["id"],))
        require(old and old["active"] and old["version"] == actor["version"],
                "다시 로그인해 주세요.", "AUTH_REQUIRED", 401)
        require(verify_password(payload.get("currentPassword"), old["password"]),
                "현재 비밀번호가 올바르지 않습니다.", "LOGIN_FAILED", 401)
        plain = validate_password(payload.get("newPassword"), old["username"])
        require(not verify_password(plain, old["password"]), "현재 비밀번호와 다른 비밀번호를 입력해 주세요.")
        self.run("""UPDATE users SET password=%s, must_change_password=false, version=version+1
                    WHERE id=%s""", (hash_password(plain), old["id"]))
        self.audit(actor, "auth", "비밀번호 변경", old["username"], {"userId": old["id"]})
        return public_user(self.user_by_id(old["id"]))
