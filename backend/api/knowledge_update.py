"""One-time bundled knowledge update, in bootstrap's existing transaction/lock.

Titles are display labels: preserve revision IDs, source hashes, chunks and past
answer snapshots when relabelling. Re-index live documents because title is an
embedding input. The settings marker is included in normal backups.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from .rag_jobs import enqueue

UPDATE_KEY = "knowledge-update:mepc-2026-11-09-v1"


def test_document_title(title: str) -> str:
    title = re.sub(r"\s*\(가상\)\s*$", "", title).strip()
    return title if title.startswith("(테스트용)") else "(테스트용) " + title


def document_payload(raw: dict, knowledge: Path) -> dict:
    document = dict(raw)
    filename = document.pop("file", None)
    meta = {"scope": "all", "status": "active", **document.pop("meta", {})}
    payload = {"expectedId": "", "meta": meta, "document": document}
    if filename:
        path = (knowledge / filename).resolve()
        if not (path.is_relative_to(knowledge.resolve()) and path.is_file()):
            raise RuntimeError(f"Seed document file not found: {filename}")
        payload["file"] = {"name": path.name,
                           "base64": base64.b64encode(path.read_bytes()).decode("ascii")}
    return payload


def apply_mepc_update(store, knowledge: Path) -> None:
    if store.one("SELECT value FROM settings WHERE key=%s", (UPDATE_KEY,)):
        return
    bundle = json.loads((knowledge / "mepc-2026.json").read_text(encoding="utf-8"))
    renamed, added = 0, 0
    # Run before importing the new MEPC files: only pre-existing titles get the prefix.
    for row in store.all("SELECT id,title,active FROM documents FOR UPDATE"):
        title = test_document_title(row["title"])
        if title != row["title"]:
            store.run("UPDATE documents SET title=%s WHERE id=%s", (title, row["id"]))
            if row["active"]:
                enqueue(store, row["id"])
            renamed += 1
    for raw in bundle:
        # Preserve existing revisions and deliberately deleted/retired documents.
        if store.one("SELECT id FROM documents WHERE logical_id=%s LIMIT 1", (raw["id"],)):
            continue
        store.save_document(document_payload(raw, knowledge))
        added += 1
    store.run("INSERT INTO settings(key,value) VALUES(%s,%s)",
              (UPDATE_KEY, json.dumps({"renamed": renamed, "added": added})))
