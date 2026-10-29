"""Evaluate Korean grounded generation with fixed seed evidence; no database access.

The default extractive mode is an offline baseline. Only --mode llm calls the
configured model. Citation checks are technical checks, never semantic grading.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" if (ROOT / "backend/api").is_dir() else ROOT
sys.path.insert(0, str(BACKEND))

import httpx

from api import config, llm

DEFAULT_CASES = Path(__file__).resolve().parent / "fixtures/korean-llm-eval.json"
DEFAULT_SEED = BACKEND / "knowledge/seed.json"


def load_cases(case_path: Path = DEFAULT_CASES, seed_path: Path = DEFAULT_SEED) -> list[dict]:
    """Resolve checked-in source selectors, rejecting drift and ambiguous IDs."""
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    documents = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases or not isinstance(documents, list):
        raise ValueError("Invalid evaluation data")
    by_id = {}
    for doc in documents:
        if not isinstance(doc, dict) or not isinstance(doc.get("id"), str) or doc["id"] in by_id:
            raise ValueError("Invalid or duplicate source document")
        by_id[doc["id"]] = doc
    result, seen = [], set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not case["id"] or case["id"] in seen
                or not isinstance(case.get("question"), str) or not case["question"].strip()
                or len(case["question"]) > 2000
                or not isinstance(case.get("expected"), dict)
                or type(case["expected"].get("insufficient")) is not bool
                or not isinstance(case["expected"].get("facts"), list)
                or not case["expected"]["facts"]
                or not all(isinstance(fact, str) and fact.strip() for fact in case["expected"]["facts"])
                or not isinstance(case.get("sources"), list) or not 1 <= len(case["sources"]) <= 5):
            raise ValueError("Invalid or duplicate evaluation case")
        seen.add(case["id"])
        evidence, source_keys = [], set()
        for source in case["sources"]:
            if (not isinstance(source, dict)
                    or any(not isinstance(source.get(key), str) or not source[key].strip()
                           for key in ("document_id", "heading", "anchor"))
                    or len(source["anchor"].strip()) < 8):
                raise ValueError("Invalid source selector")
            key = (source["document_id"], source["heading"])
            if key in source_keys:
                raise ValueError("Duplicate source selector")
            source_keys.add(key)
            doc = by_id.get(source["document_id"])
            sections = [section for section in doc.get("sections", [])
                        if section.get("heading") == source["heading"]] if doc else []
            if (len(sections) != 1 or not isinstance(sections[0].get("text"), str)
                    or source["anchor"] not in sections[0]["text"]):
                raise ValueError("Source selector no longer matches seed")
            section = sections[0]
            evidence.append({"id": f"{doc['id']}:{len(evidence) + 1}", "document_id": doc["id"],
                             "title": doc["title"], "heading": section["heading"],
                             "page": section.get("page"), "text": section["text"]})
        result.append({**case, "evidence": evidence})
    return result


def evaluate(cases: list[dict], mode: str, *, settings: config.LLMSettings | None = None) -> dict:
    if mode not in {"extractive", "llm"} or mode == "llm" and settings is None:
        raise ValueError("Model settings are required for llm mode")
    started_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for case in cases:
        evidence = case["evidence"]
        started = perf_counter()
        error_type = None
        try:
            if mode == "llm":
                statements = llm.grounded_statements(case["question"], evidence, "ko", settings)
            else:
                statements = [{"text": item["text"], "chunkId": item["id"], "quote": item["text"]}
                              for item in evidence]
            # Recheck the returned boundary so fixtures and future callers share
            # the production citation rules. Empty statements mean insufficient.
            llm.validate_statements({"insufficient": not statements, "statements": statements}, evidence)
            outcome = "answered" if statements else "insufficient"
            citation_valid = True if statements else None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            statements, outcome, citation_valid = [], "model_error", False
            # Exception class names distinguish timeouts from invalid output
            # without exposing the private upstream message, URL or headers.
            error_type = type(exc).__name__
        rows.append({"id": case["id"], "question": case["question"], "expected": case["expected"],
                     "sources": [{key: item[key] for key in ("id", "document_id", "title", "heading", "page")}
                                 for item in evidence],
                     "duration_seconds": round(perf_counter() - started, 4),
                     "outcome": outcome, "error_type": error_type,
                     "generation": "llm" if mode == "llm" and outcome != "model_error" else
                                   "extractive" if mode == "extractive" else None,
                     "model_call_attempted": mode == "llm",
                     "statements": statements, "citation_valid": citation_valid,
                     "contains_hangul": bool(re.search(r"[가-힣]", " ".join(row["text"] for row in statements))),
                     "expected_insufficient_matches": outcome == "insufficient"
                         if case["expected"]["insufficient"] else outcome == "answered",
                     "semantic_review": "pending"})
    return {"schema_version": 1, "started_at": started_at, "mode": mode,
            "execution": "real_model" if mode == "llm" else "extractive",
            "model_call_attempted": mode == "llm",
            "model": settings.model if mode == "llm" else None,
            "response_format": settings.response_format if mode == "llm" else None,
            "llm_code_sha256": hashlib.sha256(Path(llm.__file__).read_bytes()).hexdigest(),
            "evaluation_input_sha256": hashlib.sha256(json.dumps(
                cases, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest(),
            "evaluation_scope": "fixed_seed_evidence_without_retrieval_auth_or_browser",
            "semantic_review": "pending",
            "summary": {"cases": len(rows), **{key: sum(row["outcome"] == key for row in rows)
                                              for key in ("answered", "insufficient", "model_error")}},
            "results": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("extractive", "llm"), default="extractive")
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--output", type=Path, help="Create a new UTF-8 JSON file; never overwrite")
    args = parser.parse_args(argv)
    try:
        cases = load_cases()
        selected_ids = set(args.case_ids)
        if selected_ids - {case["id"] for case in cases}:
            raise ValueError("Unknown evaluation case")
        if selected_ids:
            cases = [case for case in cases if case["id"] in selected_ids]
        if args.output is not None and args.output.exists():
            raise ValueError("Output file already exists")
        settings = config.llm_settings() if args.mode == "llm" else None
        if args.mode == "llm" and settings is None:
            raise ValueError("Model configuration is missing or invalid")
        # Reserve a writable destination before spending time on model calls.
        # Exclusive creation also protects files created after the exists check.
        destination = (args.output.open("x", encoding="utf-8", newline="\n")
                       if args.output is not None else nullcontext(sys.stdout))
        with destination as stream:
            report = evaluate(cases, args.mode, settings=settings)
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 1 if report["summary"]["model_error"] else 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Evaluation failed: check cases, model configuration and a new output path. "
              "Private configuration and upstream errors are not printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
