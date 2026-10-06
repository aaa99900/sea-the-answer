"""Extract physical PDF pages as UTF-8 JSON; no OCR and no document writes."""
import json
import sys
from pathlib import Path


def extract(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("Install PDF dependency: python -m pip install -r requirements-pdf.txt") from exc
    source = Path(path)
    if source.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("PDF exceeds 128 MiB")
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported; provide an unencrypted PDF")
    if not 1 <= len(reader.pages) <= 5000:
        raise ValueError("PDF must contain 1..5000 pages")
    pages, total = [], 0
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        total += len(text)
        if total > 20000000:
            raise ValueError("Extracted PDF text exceeds 20,000,000 characters")
        pages.append({"page": number, "text": text})
    return {"pages": pages}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: python scripts/extract-pdf.py file.pdf")
        json.dump(extract(sys.argv[1]), sys.stdout, ensure_ascii=False)
    except Exception as error:
        print(f"PDF extraction failed: {error}", file=sys.stderr)
        sys.exit(1)
