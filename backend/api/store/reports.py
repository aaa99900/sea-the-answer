"""Reports: drafts, review submission and generated Noon/MRV drafts."""

from __future__ import annotations

import json
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..errors import require
from ..validation import stamp, text, utc_now


class ReportStore:
    def report(self, report_id: str) -> dict | None:
        row = self.one("SELECT * FROM reports WHERE id=%s", (report_id,))
        if not row:
            return None
        meta = self.one("SELECT owner,status,body FROM report_meta WHERE id=%s", (report_id,))
        return {**{key: stamp(value) for key, value in row.items()},
                "owner": meta["owner"] if meta else "", "status": meta["status"] if meta else "draft",
                "body": meta["body"] if meta else {}}

    def can_read_report(self, user: dict, report: dict) -> bool:
        return (user["role"] == "admin" or report["owner"] == user["id"] or report["status"] == "approved") \
            and all(self.can_read_document(user, source) for source in report["sources"])

    def reports(self, user: dict) -> list[dict]:
        return [report for row in self.all("SELECT id FROM reports ORDER BY updated_at DESC")
                if (report := self.report(row["id"])) and self.can_read_report(user, report)]

    def load_report(self, user: dict, report_id: str) -> dict:
        report = self.report(report_id)
        require(report and self.can_read_report(user, report), "보고서를 찾을 수 없거나 열람 권한이 없습니다.", "NOT_FOUND", 404)
        return report

    def save_report(self, user: dict, payload: dict) -> dict:
        self.permit(user, ("admin", "operator"))
        require(isinstance(payload, dict), "보고서가 필요합니다.")
        report_id = payload.get("id") or str(uuid4())
        locked = self.one("SELECT version FROM reports WHERE id=%s FOR UPDATE", (report_id,))
        old = self.report(report_id) if locked else None
        if old:
            require(user["role"] == "admin" or old["owner"] == user["id"], "본인의 초안만 수정할 수 있습니다.", "FORBIDDEN", 403)
            require(old["status"] == "draft", "검토 중이거나 승인된 보고서는 새 초안으로 복사해 주세요.")
        sources = payload.get("sources")
        require(isinstance(sources, list) and len(sources) <= 100
                and all(isinstance(item, str) and self.can_read_document(user, item) for item in sources),
                "열람할 수 없는 문서가 근거에 포함되어 있습니다.", "FORBIDDEN", 403)
        require((locked or {}).get("version", 0) == payload.get("version"), "다른 창에서 초안이 변경되었습니다.", "VERSION_CONFLICT", 409)
        title = text(payload.get("title"), "제목", 120)
        content = text(payload.get("text"), "내용", 200000)
        require(payload.get("type") in ("규정 검토", "일일 운항", "배출량 검토", "종합 검토"), "보고서 유형을 확인해 주세요.")
        body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
        require(len(json.dumps(body, ensure_ascii=False)) < 50000, "보고서 추가 정보가 너무 큽니다.")
        version, updated = (old or {}).get("version", 0) + 1, utc_now()
        if old:
            saved = self.one("""UPDATE reports SET title=%s,type=%s,text=%s,sources=%s,
                version=version+1,updated_at=%s WHERE id=%s AND version=%s RETURNING version""",
                (title, payload["type"], content, Jsonb(list(dict.fromkeys(sources))), updated,
                 report_id, old["version"]))
        else:
            saved = self.one("""INSERT INTO reports VALUES(%s,%s,%s,%s,%s,1,%s)
                ON CONFLICT DO NOTHING RETURNING version""",
                (report_id, title, payload["type"], content, Jsonb(list(dict.fromkeys(sources))), updated))
        require(saved, "다른 창에서 초안이 변경되었습니다.", "VERSION_CONFLICT", 409)
        self.run("""INSERT INTO report_meta VALUES(%s,%s,'draft',%s)
            ON CONFLICT(id) DO UPDATE SET body=excluded.body""",
            (report_id, old["owner"] if old else user["id"], Jsonb(body)))
        self.audit(user, "report", "초안 저장", report_id, {"title": title, "version": version})
        return self.report(report_id)

    def submit_report(self, user: dict, payload: dict) -> dict:
        self.permit(user, ("admin", "operator"))
        self.one("SELECT version FROM reports WHERE id=%s FOR UPDATE", (payload.get("id", ""),))
        report = self.load_report(user, payload.get("id", ""))
        require(report["version"] == payload.get("version"), "보고서가 변경되었습니다.", "VERSION_CONFLICT", 409)
        require(user["role"] == "admin" or report["owner"] == user["id"], "본인의 보고서만 검토 요청할 수 있습니다.", "FORBIDDEN", 403)
        require(report["status"] == "draft", "이미 검토 요청 또는 승인된 보고서입니다.")
        change_id = str(uuid4())
        self.run("UPDATE report_meta SET status='review' WHERE id=%s", (report["id"],))
        self.run("INSERT INTO changes VALUES(%s,%s,%s,'report.approve',%s,'pending',NULL,NULL,'')",
                 (change_id, utc_now(), user["id"], Jsonb({"id": report["id"], "version": report["version"], "title": report["title"]})))
        self.audit(user, "report", "보고서 검토 요청", report["id"])
        return {"id": change_id}

    def generate_report(self, user: dict, payload: dict) -> dict:
        require(payload.get("template") in ("noon", "mrv"), "보고서 양식을 선택해 주세요.")
        summary = self.operation_summary(payload)
        require(summary["count"] > 0, "선택 기간의 운항 기록이 없습니다.")
        if payload["template"] == "noon":
            last = summary["rows"][-1]
            summary = self.operation_summary({"ship": payload["ship"], "from": last["date"], "to": last["date"]})
        ship, rows = summary["ship"], summary["rows"]
        label = "Noon Report" if payload["template"] == "noon" else "MRV 검토 보고서"
        lines = [f"# {label}", "", "상태: 검토용 초안" + (" · 가상 예시 데이터 포함" if summary["sample"] else ""),
                 f"선박: {ship['name']}", f"기간: {summary['from']} ~ {summary['to']}", "", "## 운항·연료 기록"]
        lines += [f"{row['date']} | 연료 {row['fuel']} t | CO₂ {row['fuel'] * row['factor']} t | 거리 {row['distance']} nm" for row in rows]
        lines += ["", "## 집계", f"연료 합계: {summary['fuel']} t", f"CO₂ 합계: {summary['emission']} t",
                  f"거리 합계: {summary['distance']} nm", f"CII: 산출 불가 — {summary['cii']['reason']}"]
        return self.save_report(user, {"title": f"{ship['name']} · {label} · {summary['from']}",
                                       "type": "일일 운항" if payload["template"] == "noon" else "배출량 검토",
                                       "text": "\n".join(lines), "sources": [], "version": 0,
                                       "body": {"template": payload["template"], "ship": ship["id"],
                                                "from": summary["from"], "to": summary["to"],
                                                "recordIds": [{"id": row["id"], "version": row["version"]} for row in rows],
                                                "sample": summary["sample"]}})
