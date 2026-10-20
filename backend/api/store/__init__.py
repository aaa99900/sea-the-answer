"""`Workspace`: one PostgreSQL session with every domain operation.

Each domain lives in its own mixin module; this class only composes them, so callers keep
using `db.save_document(...)`, `db.answer(...)` and so on.
"""

from __future__ import annotations

import base64
import json
import os

import psycopg

from ..config import BACKEND_DIR
from ..errors import ApiError
from ..validation import text
from .answers import AnswerStore
from .backups import BACKUP_TABLES, BackupStore
from .base import Database
from .changes import ChangeStore
from .documents import DocumentStore
from .operations import OperationStore
from .reports import ReportStore
from .tools import TOOL_DEFINITIONS, ToolStore
from .users import UserStore

__all__ = ["BACKUP_TABLES", "TOOL_DEFINITIONS", "Workspace"]


class Workspace(Database, UserStore, DocumentStore, OperationStore, ChangeStore, ReportStore,
                AnswerStore, ToolStore, BackupStore):
    def bootstrap(self) -> None:
        try:
            self.one("SELECT 1 FROM settings LIMIT 1")
        except psycopg.Error as exc:
            raise ApiError(503, "SCHEMA_NOT_READY", "DB 마이그레이션이 적용되지 않았습니다. migrations/를 dbmate로 적용해 주세요.") from exc
        self.run("INSERT INTO settings(key,value) VALUES('autoBackup','daily') ON CONFLICT(key) DO NOTHING")
        if not self.one("SELECT 1 FROM users LIMIT 1") and os.environ.get("HAEDAP_BOOTSTRAP_PASSWORD"):
            username = text(os.environ.get("HAEDAP_BOOTSTRAP_USERNAME"), "초기 관리자 아이디", 40)
            # Use the same validation and lifecycle path as administrator provisioning.
            self.save_user({"id": "bootstrap", "name": "서버 초기 설정", "role": "admin"}, {
                "username": username, "name": os.environ.get("HAEDAP_BOOTSTRAP_NAME") or username,
                "role": "admin", "password": os.environ["HAEDAP_BOOTSTRAP_PASSWORD"],
            })
        if not self.one("SELECT 1 FROM documents LIMIT 1"):
            knowledge = BACKEND_DIR / "knowledge"
            for raw in json.loads((knowledge / "seed.json").read_text(encoding="utf-8")):
                payload = {"expectedId": "", "meta": {"scope": "all", "status": "active"}}
                # "file" names an original PDF under knowledge/ (scripts/build_seed_documents.py).
                file_name = raw.pop("file", None)
                if file_name:
                    path = (knowledge / file_name).resolve()
                    if not (path.is_relative_to(knowledge.resolve()) and path.is_file()):
                        raise RuntimeError(f"Seed document file not found: {file_name}")
                    payload["file"] = {"name": path.name, "base64": base64.b64encode(path.read_bytes()).decode("ascii")}
                self.save_document({**payload, "document": raw})
