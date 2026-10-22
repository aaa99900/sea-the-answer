"""Admin changes to source data, the approval queue and its review."""

from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Jsonb

from ..errors import ApiError, require
from ..validation import stamp, utc_now
from .backups import BackupStore


class ChangeStore:
    def _maritime_links_for_ship_change(self, ship_id: str) -> list[dict] | None:
        ready = self.one("""SELECT EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid=to_regclass('maritime_data.vessels')
              AND attname='ship_id' AND NOT attisdropped
        ) AS ready""")
        if not ready["ready"]:
            return None
        # Match restore/link CLI lock order and prevent a new offline mapping
        # from racing the app's identity check. Source records stay unchanged.
        self.run("SET LOCAL lock_timeout = '5s'")
        self.run("LOCK TABLE maritime_data.vessels IN SHARE ROW EXCLUSIVE MODE")
        return self.all("""SELECT vessel_id,imo_number FROM maritime_data.vessels
            WHERE ship_id=%s""", (ship_id,))

    def apply_change(self, kind: str, payload: dict) -> dict:
        if kind == "document.save":
            return self.save_document(payload)
        if kind == "document.delete":
            return self.delete_document(payload["id"])
        if kind == "ship.save":
            ship = self.validate_ship(payload)
            links = self._maritime_links_for_ship_change(ship["id"])
            old = self.one("SELECT version,body FROM ships WHERE id=%s FOR UPDATE" if links is not None
                           else "SELECT version FROM ships WHERE id=%s", (ship["id"],))
            require((old or {}).get("version", 0) == payload.get("version", 0), "선박 정보가 변경되었습니다.", "VERSION_CONFLICT", 409)
            for link in links or []:
                require(old and BackupStore._maritime_ship_matches({**link, "body": old["body"]}, ship),
                        "해사 데이터 연결과 다른 선박 식별정보로 변경할 수 없습니다. 연결을 검토·해제한 후 다시 시도해 주세요.",
                        "MARITIME_SHIP_IDENTITY_CONFLICT", 409)
            saved = (self.one("UPDATE ships SET body=%s,version=version+1 WHERE id=%s AND version=%s RETURNING version",
                              (Jsonb(ship), ship["id"], old["version"])) if old else
                     self.one("INSERT INTO ships(id,body,version) VALUES(%s,%s,1) ON CONFLICT DO NOTHING RETURNING version",
                              (ship["id"], Jsonb(ship))))
            require(saved, "선박 정보가 변경되었습니다.", "VERSION_CONFLICT", 409)
            return ship
        if kind in ("operation.save", "operation.import"):
            result = {"rows": [self.validate_operation(payload)], "errors": []} if kind == "operation.save" else self.validate_rows(payload.get("rows"))
            require(not result["errors"], "\n".join(f"{item['row']}행: {item['message']}" for item in result["errors"]))
            for row in result["rows"]:
                if row["version"]:
                    saved = self.one("""UPDATE operations SET ship=%s,date=%s,body=%s,version=version+1
                        WHERE id=%s AND version=%s RETURNING version""",
                        (row["ship"], row["date"], Jsonb(row), row["id"], row["version"]))
                else:
                    saved = self.one("""INSERT INTO operations VALUES(%s,%s,%s,%s,1)
                        ON CONFLICT DO NOTHING RETURNING version""",
                        (row["id"], row["ship"], row["date"], Jsonb(row)))
                require(saved, "운항 기록이 변경되었습니다.", "VERSION_CONFLICT", 409)
            return {"count": len(result["rows"])}
        if kind == "operation.delete":
            old = self.one("SELECT version FROM operations WHERE id=%s", (payload.get("id"),))
            require(old and old["version"] == payload.get("version"), "운항 기록이 변경되었습니다.", "VERSION_CONFLICT", 409)
            deleted = self.one("DELETE FROM operations WHERE id=%s AND version=%s RETURNING id",
                               (payload["id"], payload["version"]))
            require(deleted, "운항 기록이 변경되었습니다.", "VERSION_CONFLICT", 409)
            return {"id": payload["id"]}
        if kind == "report.approve":
            report = self.report(payload["id"])
            require(report and report["version"] == payload.get("version"), "보고서가 변경되었습니다.", "VERSION_CONFLICT", 409)
            require(report["status"] == "review", "검토 요청된 보고서만 승인할 수 있습니다.")
            self.run("UPDATE report_meta SET status='approved' WHERE id=%s", (payload["id"],))
            return {"id": payload["id"]}
        raise ApiError(400, "INVALID_INPUT", "지원하지 않는 변경입니다.")

    def change(self, user: dict, kind: str, payload: dict) -> dict:
        self.permit(user)
        require(kind in ("document.save", "document.delete", "ship.save", "operation.save", "operation.import", "operation.delete"),
                "지원하지 않는 변경입니다.")
        require(isinstance(payload, dict), "변경 내용이 필요합니다.")
        result = self.apply_change(kind, payload)
        change_id, at = str(uuid4()), utc_now()
        self.run("INSERT INTO changes VALUES(%s,%s,%s,%s,%s,'approved',%s,%s,%s)",
                 (change_id, at, user["id"], kind, Jsonb(payload), user["id"], at, "관리자 직접 반영"))
        self.audit(user, "change", "변경 즉시 반영", kind, {"id": change_id, "result": result})
        return {"id": change_id, "status": "approved", "result": result}

    def list_changes(self, user: dict) -> list[dict]:
        self.permit(user)
        rows = self.all("""SELECT c.*,u.name AS actor_name FROM changes c
            LEFT JOIN users u ON u.id=c.actor ORDER BY c.at DESC LIMIT 200""")
        return [{**{key: stamp(value) for key, value in row.items()},
                 "actor_name": row["actor_name"] or "이전 사용자"} for row in rows]

    def review_change(self, user: dict, payload: dict) -> dict:
        self.permit(user)
        change = self.one("SELECT * FROM changes WHERE id=%s", (payload.get("id"),))
        if change and change["kind"] == "report.approve":
            # Same lock order as report save/submit/delete; recheck after waiting.
            self.one("SELECT id FROM reports WHERE id=%s FOR UPDATE", (change["payload"]["id"],))
            change = self.one("SELECT * FROM changes WHERE id=%s", (payload.get("id"),))
        require(change and change["status"] == "pending", "처리할 승인 요청이 없습니다.", "VERSION_CONFLICT", 409)
        decision = payload.get("decision")
        require(decision in ("approve", "reject"), "승인 또는 반려를 선택해 주세요.")
        if decision == "approve":
            self.apply_change(change["kind"], change["payload"])
        elif change["kind"] == "report.approve":
            self.run("UPDATE report_meta SET status='draft' WHERE id=%s", (change["payload"]["id"],))
        self.run("UPDATE changes SET status=%s,reviewer=%s,reviewed_at=%s,note=%s WHERE id=%s",
                 ("approved" if decision == "approve" else "rejected", user["id"], utc_now(), str(payload.get("note") or "")[:1000], change["id"]))
        self.audit(user, "change", "승인" if decision == "approve" else "반려", change["kind"])
        return {"ok": True}
