"""Rebuild file-backed entries of backend/knowledge/seed.json from the original PDFs.

The PDFs in backend/knowledge/documents/ are redistributable originals (Korean
statutes from law.go.kr, which are not copyright-protected under Korean
Copyright Act art. 7; and a U.S. Government work from navcen.uscg.gov).
Each generated entry keeps a "file" field so the backend stores the original
PDF next to the extracted text when it seeds an empty database.

Requires poppler's `pdftotext` (macOS: `brew install poppler`, Ubuntu:
`apt install poppler-utils`). Run from the repository root:

    cd backend && uv run python ../scripts/build_seed_documents.py

Entries without a "file" field (hand-written summaries, the glossary,
samples) are left untouched. Re-running with unchanged PDFs is idempotent.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "backend" / "knowledge"
SEED = KNOWLEDGE / "seed.json"

LAW_URL = "https://www.law.go.kr/%EB%B2%95%EB%A0%B9/"
KOREAN_LAWS = [
    # (id, file, law name, url-encoded name)
    ("kr-marine-environment-management-act", "kr-marine-environment-management-act.pdf", "해양환경관리법",
     "%ED%95%B4%EC%96%91%ED%99%98%EA%B2%BD%EA%B4%80%EB%A6%AC%EB%B2%95"),
    ("kr-ship-safety-act", "kr-ship-safety-act.pdf", "선박안전법",
     "%EC%84%A0%EB%B0%95%EC%95%88%EC%A0%84%EB%B2%95"),
    ("kr-maritime-traffic-safety-act", "kr-maritime-traffic-safety-act.pdf", "해상교통안전법",
     "%ED%95%B4%EC%83%81%EA%B5%90%ED%86%B5%EC%95%88%EC%A0%84%EB%B2%95"),
    ("kr-ship-officers-act", "kr-ship-officers-act.pdf", "선박직원법",
     "%EC%84%A0%EB%B0%95%EC%A7%81%EC%9B%90%EB%B2%95"),
]
USCG = {
    "id": "uscg-navigation-rules-handbook",
    "file": "uscg-navigation-rules-handbook-2024.pdf",
    "title": "USCG Navigation Rules and Regulations Handbook (COLREGS · Inland Rules)",
    "url": "https://www.navcen.uscg.gov/sites/default/files/pdf/navRules/Handbook/"
           "Nav%20Rules%20Handbook_Corrected_08-12-2024.pdf",
    "reference": "72 COLREGS · 33 CFR Part 83 (corrected 2024-08-12)",
    "version": "2024-08-12",
}

ARTICLE = re.compile(r"^(제\d+조(?:의\d+)?)\(([^)]{1,80})\)\s*(.*)$")
DELETED = re.compile(r"^제\d+조(?:의\d+)?\s*삭제")
CHAPTER = re.compile(r"^(제\d+(?:장|절)(?:의\d+)?\s+[^<\[]+)")
ITEM_START = re.compile(r"^(?:[①-⑳]|\d+(?:의\d+)?\.\s|[가-하]\.\s|\d+\)\s|\[|<)")
HEADER = re.compile(r"\[시행\s*([\d.\s]+)\]\s*\[법률\s*제(\d+)호")


def pdf_pages(path: Path) -> list[str]:
    try:
        out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"],
                             check=True, capture_output=True, text=True).stdout
    except FileNotFoundError:
        sys.exit("pdftotext not found: install poppler (brew install poppler / apt install poppler-utils)")
    return out.split("\f")


def join_korean(lines: list[str]) -> str:
    """Join PDF-wrapped lines; keep a newline before list markers and notes."""
    text = ""
    for line in lines:
        if not text:
            text = line
        elif ITEM_START.match(line):
            text += "\n" + line
        elif re.search(r"[A-Za-z0-9,.)]$", text) and re.match(r"[A-Za-z0-9(]", line):
            text += " " + line
        else:
            # Korean wraps may split inside a word; joining without a space keeps
            # every original word intact for substring search.
            text += line
    return text.strip()


def korean_law(doc_id: str, filename: str, name: str, encoded: str, reviewed: str) -> dict:
    pages = pdf_pages(KNOWLEDGE / "documents" / filename)
    noise = {name, "법제처", "국가법령정보센터"}
    header = HEADER.search(" ".join(pages[0].split()))
    if not header:
        sys.exit(f"{filename}: 시행일·법률 번호를 찾지 못했습니다.")
    effective = "-".join(f"{int(p):02d}" for p in header.group(1).replace(" ", "").strip(".").split("."))
    number = header.group(2)
    sections, chapter, current, started = [], "", None, False

    def flush():
        if current and not current["deleted"]:
            body = join_korean(current["lines"])
            heading = (f"{chapter} · " if chapter else "") + current["label"]
            sections.append({"heading": heading[:200], "text": body[:20000], "page": current["page"]})

    for page_no, page in enumerate(pages, 1):
        for raw in page.splitlines():
            line = raw.strip()
            if not line or line in noise or line.isdigit():
                continue
            if line.startswith("부칙"):
                flush()
                current = None
                break
            match_chapter = CHAPTER.match(line)
            if match_chapter and not ARTICLE.match(line):
                started = True
                flush()
                current = None
                chapter = match_chapter.group(1).strip()
                continue
            match = ARTICLE.match(line)
            if match or DELETED.match(line):
                started = True
                flush()
                label = f"{match.group(1)}({match.group(2)})" if match else line.split()[0]
                current = {"label": label, "lines": [line], "page": page_no, "deleted": not match}
                continue
            if started and current:
                current["lines"].append(line)
        else:
            continue
        break
    flush()
    return {
        "id": doc_id,
        "title": f"{name} (법률 제{number}호)",
        "kind": "onboard",
        "url": LAW_URL + encoded,
        "reference": f"법률 제{number}호 · 시행 {effective.replace('-', '. ')}. · 국가법령정보센터 원문",
        "version": f"{effective}-law-{number}",
        "reviewedAt": reviewed,
        "language": "ko",
        "file": f"documents/{filename}",
        "sections": sections,
    }


def uscg_handbook(reviewed: str) -> dict:
    pages = pdf_pages(KNOWLEDGE / "documents" / USCG["file"])
    sections = []
    for page_no, page in enumerate(pages, 1):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        lines = [line for line in lines if not line.isdigit()]
        if sum(len(line) for line in lines) < 200:
            continue  # covers, blank and figure-only pages
        side = next((s for s in ("INTERNATIONAL", "INLAND") if any(f"—{s}—" in line for line in lines)), "")
        rules = list(dict.fromkeys(m.group(0) for line in lines
                                   for m in [re.match(r"^(?:Rule \d+|Annex [IVX]+)\b", line)] if m))
        span = rules[0] + (f"–{rules[-1].split()[-1]}" if len(rules) > 1 else "") if rules else ""
        heading = " · ".join(part for part in (f"p.{page_no}", side.title(), span) if part)
        text = ""
        for line in lines:
            if not text:
                text = line
            elif re.match(r"^(?:\([a-z]+\)|\([ivx]+\)|Rule \d+|§|Annex )", line):
                text += "\n" + line
            elif text.endswith("-") and not text.endswith(" -"):
                text = text[:-1] + line
            else:
                text += " " + line
        sections.append({"heading": heading[:200], "text": text[:20000], "page": page_no})
    return {**{k: v for k, v in USCG.items() if k != "file"}, "kind": "onboard", "reviewedAt": reviewed,
            "language": "en", "file": f"documents/{USCG['file']}", "sections": sections}


def main() -> None:
    reviewed = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    built = [korean_law(*law, reviewed) for law in KOREAN_LAWS] + [uscg_handbook(reviewed)]
    for entry in built:
        entry["title"] = "(테스트용) " + re.sub(r"\s*\(가상\)\s*$", "", entry["title"]).strip()
    by_id = {entry["id"]: entry for entry in built}
    merged = [by_id.pop(entry["id"], entry) for entry in seed]
    merged += list(by_id.values())
    for entry in built:
        if not entry["sections"] or len(entry["sections"]) > 1500:
            sys.exit(f"{entry['id']}: 절 수 {len(entry['sections'])}개가 허용 범위(1~1500)를 벗어났습니다.")
        print(f"{entry['id']}: {len(entry['sections'])} sections")
    SEED.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
