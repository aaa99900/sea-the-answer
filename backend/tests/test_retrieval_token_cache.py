"""Token reuse must preserve current content, access boundaries and scores."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from api import rag_retrieval as rag
from api.store.documents import DocumentStore


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    cache = rag._TokenCache()
    monkeypatch.setattr(rag, "_CHUNK_TOKENS", cache)
    return cache


def chunk(id="a", text="fuel emission", **fields):
    return {"id": id, "document_id": id, "title": "", "reference": "", "heading": "", "text": text, **fields}


def test_same_content_reuses_tokens_and_returned_lists_cannot_mutate_cache(monkeypatch):
    calls = []
    def analyze(value):
        calls.append(value)
        return ["fuel", "fuel", "emission"]
    monkeypatch.setattr(rag, "tokenize", analyze)
    first = rag.chunk_tokens(chunk())
    first.clear()
    assert rag.chunk_tokens(chunk(id="different-id")) == ["fuel", "fuel", "emission"]
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["text", "title", "heading", "reference"])
def test_any_searchable_content_change_is_reanalyzed(monkeypatch, field):
    calls = []
    monkeypatch.setattr(rag, "tokenize", lambda text: calls.append(text) or text.split())
    old = chunk()
    rag.chunk_tokens(old)
    revised = {**old, field: "new terminology"}
    assert rag.chunk_tokens(revised) != rag.chunk_tokens(old)
    assert len(calls) == 2


def test_cache_has_both_entry_and_accounted_size_limits():
    cache = rag._TokenCache(max_entries=2)
    cache.put(b"a", ["alpha"])
    cache.put(b"b", ["beta"])
    assert cache.get(b"a") == ("alpha",)  # b is now least recently used.
    cache.put(b"c", ["gamma"])
    assert cache.get(b"b") is None and cache.get(b"a") == ("alpha",)
    one_entry_size = rag._TokenCache()
    one_entry_size.put(b"a", ["alpha"])
    small = rag._TokenCache(max_bytes=one_entry_size.size_bytes)
    for key in (b"a", b"b", b"c"):
        small.put(key, ["alpha"])
    assert len(small.entries) == 1 and small.size_bytes <= small.max_bytes
    small.put(b"large", ["z" * 10000])
    assert small.get(b"large") is None
    small.clear()
    assert small.size_bytes == 0 and not small.entries


def test_concurrent_cache_access_stays_bounded_and_returns_immutable_values():
    cache = rag._TokenCache(max_entries=4, max_bytes=4096)
    def use(i):
        key = str(i % 10).encode()
        cache.put(key, ["token"] * 4)
        result = cache.get(key)
        assert result is None or result == ("token",) * 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(use, range(100)))
    assert len(cache.entries) <= 4 and 0 <= cache.size_bytes <= cache.max_bytes
    assert cache.size_bytes == sum(size for _, size in cache.entries.values())


def test_caching_keeps_scores_order_and_current_metadata(monkeypatch):
    rows = [chunk("a", "fuel fuel emissions", page=7), chunk("b", "fuel ballast"), chunk("c", "ballast")]
    expected = rag.retrieve("fuel", rows)
    # Simulate a changed row with identical searchable text: return the new row,
    # not a stale result held by the cache.
    current = deepcopy(rows)
    current[0].update(page=99, meta={"scope": "operator"})
    actual = rag.retrieve("fuel", current)
    assert [(r["id"], r["score"]) for r in actual] == [(r["id"], r["score"]) for r in expected]
    assert next(r for r in actual if r["id"] == "a")["page"] == 99
    monkeypatch.setattr(rag, "_CHUNK_TOKENS", rag._TokenCache(max_bytes=0))
    assert rag.retrieve("fuel", current) == actual


def test_warm_cache_respects_revoked_access_deleted_rows_and_current_idf(monkeypatch):
    rows = [chunk("public", "fuel ballast", meta={"scope": "all", "status": "active"}),
            chunk("private", "fuel fuel fuel", meta={"scope": "admin", "status": "active"})]
    for item in rows:
        item.update(kind="onboard", reviewed_at="2026-10-28")
    store = DocumentStore()
    store.all = lambda *args: rows
    admin = store.search({"role": "admin"}, "fuel")
    assert {r["id"] for r in admin} == {"public", "private"}
    crew = store.search({"role": "operator"}, "fuel")
    assert [r["id"] for r in crew] == ["public"]
    rows[0]["meta"]["scope"] = "admin"
    assert store.search({"role": "operator"}, "fuel") == []
    rows[0]["meta"]["scope"] = "all"
    rows[0]["meta"]["status"] = "deleted"
    assert store.search({"role": "operator"}, "fuel") == []
    # A cached document excluded from the current candidate set cannot affect IDF.
    cached = rag.retrieve("fuel", [rows[1]])
    monkeypatch.setattr(rag, "_CHUNK_TOKENS", rag._TokenCache(max_bytes=0))
    assert rag.retrieve("fuel", [rows[1]]) == cached


def test_selected_document_search_ignores_other_warmed_document_tokens(monkeypatch):
    rows = [chunk("selected", "fuel ballast"), chunk("other", "fuel fuel fuel")]
    for item in rows:
        item.update(kind="onboard", reviewed_at="2026-10-28", meta={"scope": "all", "status": "active"})
    store = DocumentStore()
    store.allowed_document_ids = lambda user: ["selected", "other"]

    def read(sql, params=()):
        if params:
            assert "d.id = ANY(%s)" in sql
            return [r for r in rows if r["document_id"] in params[0]]
        return rows

    store.all = read
    user = {"role": "admin"}
    assert len(store.search(user, "fuel")) == 2  # Warm both documents first.
    scoped = store.search(user, "fuel", document_ids=["selected"])
    assert [r["id"] for r in scoped] == ["selected"]
    monkeypatch.setattr(rag, "_CHUNK_TOKENS", rag._TokenCache(max_bytes=0))
    assert store.search(user, "fuel", document_ids=["selected"]) == scoped
