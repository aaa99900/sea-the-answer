"""Page-local, deterministic text preprocessing; no DB, web or PDF dependency.

Input text has already been extracted/reviewed by the PDF upload UI. Preserve
tables and legal numbers rather than guessing missing layout or formulae.
"""

from __future__ import annotations

import re
from collections import defaultdict


_RUNNING_HEADER = re.compile(r"^(?:Part\s+\d+[A-Z]?|Chapter\s+\d+|Section\s+\d+)\s+\S")
_ABS_FOOTER = re.compile(r"^ABS\s+RULES FOR BUILDING AND CLASSING\b.+[•·]\s*\d{4}\s+\d+$")
_CLAUSE = re.compile(r"^[1-9]\d{0,2}(?:\.\d{1,3}){0,4}\s+[A-Z가-힣]")
_LABEL = re.compile(r"^(?:TABLE|FIGURE)\s+\d+\b", re.I)
_SENTENCE_END = re.compile(r"[.!?。！？][\"'’”)]*(?=\s)")
_TOC_LEADER = re.compile(r"(?:\.{3,}|…{2,})\s*(?:\d+|[ivxlcdm]+)?\s*$", re.I)
_PAGE_NUMBER = re.compile(r"(?:\d+|[ivxlcdm]+)$", re.I)
_TOC_TITLE = re.compile(r"(?:table of contents|contents|목\s*차)(?:\s*\(continued\))?", re.I)


def _is_toc(lines: list[str]) -> bool:
    populated = [_key(line) for line in lines if line.strip()]
    leaders = sum(bool(_TOC_LEADER.search(line)) for line in populated)
    # Continued TOC pages often have no CONTENTS label. A single cross-reference
    # or an ellipsis in prose must not turn an ordinary page into a TOC.
    return leaders >= 3 or (leaders >= 1 and any(_TOC_TITLE.fullmatch(s) for s in populated[:6]))


def _toc_blocks(lines: list[str]) -> list[str]:
    """Keep wrapped entries and detached destination numbers together."""
    blocks, pending = [], []
    for line in lines:
        pending.append(line)
        value = _key(line)
        leader = _TOC_LEADER.search(value)
        ends_entry = bool(leader and re.search(r"(?:\d+|[ivxlcdm]+)$", value, re.I))
        if _PAGE_NUMBER.fullmatch(value) and len(pending) > 1:
            ends_entry = True
        # A leader without a page number continues onto the next line.
        if ends_entry:
            blocks.append("\n".join(pending).strip())
            pending = []
    if pending:
        blocks.append("\n".join(pending).strip())
    return [block for block in blocks if block]


def _pack_toc(lines: list[str], limit: int):
    current = ""
    for block in _toc_blocks(lines):
        if current and len(current) + 1 + len(block) > limit:
            yield current
            current = ""
        # Pathological entries longer than the cap still obey the size limit.
        pieces = list(_split_block(block, limit, True))
        for piece in pieces[:-1]:
            yield piece
        if pieces:
            current = current + "\n" + pieces[-1] if current else pieces[-1]
    if current:
        yield current


def _key(line: str) -> str:
    return " ".join(line.split())


def _lines(text: str) -> list[str]:
    # Do not collapse columns, dehyphenate words, or change legal numbers.
    return [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n")
            .replace("\u00a0", " ").split("\n")]


def _edges(lines: list[str]):
    populated = [i for i, line in enumerate(lines) if line.strip()]
    for i in populated[:3]:
        key = _key(lines[i])
        if _RUNNING_HEADER.match(key):
            yield i, key
    for i in populated[-2:]:
        key = _key(lines[i])
        if _ABS_FOOTER.fullmatch(key):
            yield i, re.sub(r"\s+\d+$", " <page>", key)


def _is_heading(line: str) -> bool:
    value = _key(line)
    # Dot leaders are TOC entries, not new clauses. Short sentences/list bodies
    # ending in punctuation must not be mistaken for section titles.
    if not value or len(value) > 140 or "..." in value or value.endswith((".", ";", ":", "?", "!")):
        return False
    return bool(_LABEL.match(value) or (_CLAUSE.match(value) and len(value.split()) <= 16))


def _heading(base: str, label: str) -> str:
    label = _key(label)
    if base == label or re.fullmatch(r"(?:페이지\s*(?:\d+|미지정)|본문)", base):
        return label[:200]
    return (base[:max(0, 197 - len(label))] + " / " + label)[:200]


def _split_block(content: str, limit: int, table: bool):
    """Yield bounded pieces without losing any non-whitespace character."""
    content = content.strip()
    while len(content) > limit:
        window = content[:limit + 1]
        paragraphs = [m.start() for m in re.finditer(r"\n\s*\n", window)]
        sentences = [m.end() for m in _SENTENCE_END.finditer(window) if m.end() <= limit]
        lines = [m.start() for m in re.finditer(r"\n", window)]
        spaces = [m.start() for m in re.finditer(r"\s", window)]
        choices = [paragraphs, lines, spaces] if table else [paragraphs, sentences, lines, spaces]
        # Prefer a natural boundary without producing an isolated heading at
        # the very beginning of an otherwise long paragraph/table.
        cut = next((points[-1] for points in choices if points and points[-1] >= limit * .4), None)
        if cut is None:
            cut = spaces[-1] if spaces and spaces[-1] > 0 else limit
        yield content[:cut].strip()
        content = content[cut:].strip()
    if content:
        yield content


def preprocess_sections(sections: list[dict], max_chars: int = 900) -> list[dict]:
    """Return {page, heading, text} chunks, retaining input section/page order.

    Call after the existing API input validation. Missing page numbers remain
    None; repeated sections on one physical page do not count as multiple
    pages when detecting running headers. The caller owns IDs and persistence.
    """
    if type(max_chars) is not int or max_chars < 32:
        raise ValueError("max_chars must be an integer of at least 32")
    prepared = [(section, _lines(section["text"])) for section in sections]
    appearances = defaultdict(set)
    for section, lines in prepared:
        page = section.get("page")
        if type(page) is int:
            for _, key in _edges(lines):
                appearances[key].add(page)
    repeated = {key for key, pages in appearances.items() if len(pages) >= 3}
    result = []
    for section, lines in prepared:
        removed = {i for i, key in _edges(lines) if key in repeated}
        base = section["heading"]
        # Keep the most specific running section title as metadata even when
        # suppressing its repeated copy in the body.
        context = [lines[i] for i in sorted(removed) if _RUNNING_HEADER.match(_key(lines[i]))]
        if context:
            base = _heading(base, context[-1])
        kept = [line for i, line in enumerate(lines) if i not in removed]
        if _is_toc(kept):
            result.extend({"page": section.get("page"), "heading": base, "text": piece}
                          for piece in _pack_toc(kept, max_chars))
            continue
        heading = base
        block = []

        def flush():
            content = "\n".join(block).strip()
            # Preserve row boundaries in labelled tables or numeric grids.
            table = bool(_LABEL.match(_key(content.split("\n")[0]))) if content else False
            table = table or bool(re.search(r"(?:\d+(?:\.\d+)?[ \t]+){3}", content))
            for piece in _split_block(content, max_chars, table):
                result.append({"page": section.get("page"), "heading": heading, "text": piece})

        for i, line in enumerate(lines):
            if i in removed:
                continue
            if _is_heading(line):
                only_titles = bool(block) and all(not s.strip() or _is_heading(s) for s in block)
                if only_titles and len("\n".join(block + [line])) < max_chars * .4:
                    # A parent title followed directly by a child title shares
                    # the child's explanation; retain both labels as metadata.
                    heading = _heading(heading, line)
                else:
                    flush()
                    block = []
                    heading = _heading(base, line)
            block.append(line)
        flush()
    return result
