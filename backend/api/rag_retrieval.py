"""Request-local BM25 retrieval over already-authorized chunks; no DB or web IO."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from threading import Lock

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

from .rag_vocabulary import KOREAN_TERMS, SEARCH_SYNONYMS, STOPWORDS

_PARTS = re.compile(r"[가-힣]+(?:\s+[가-힣]+)*|[a-z]+[a-z0-9]*|\d+(?:\.\d+)*[a-z]?")
_SEARCH_FIELDS = ("title", "reference", "heading", "text")
_KIWI_LOCK = Lock()


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    analyzer = Kiwi(num_workers=1, model_type="cong")
    for word in KOREAN_TERMS:
        analyzer.add_user_word(word, "NNP")
    return analyzer


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower()


def tokenize(value: str) -> list[str]:
    """Shared query/corpus morphology, preserving frequency and numeric labels."""
    tokens = []
    for part in _PARTS.findall(_normalize(value)):
        if not ("가" <= part[0] <= "힣"):
            tokens.append(part)
            continue
        # Only the analyzer/dictionary is shared; no document text or index is
        # cached. Lock also prevents duplicate lazy initialization on requests.
        with _KIWI_LOCK:
            morphemes = _kiwi().tokenize(part)
        for token in morphemes:
            tag = token.tag.split("-")[0]
            if tag in {"NNG", "NNP", "NR", "VV", "VA", "MAG", "XR"} or token.form == "않":
                tokens.append(token.form)
    return [t for t in tokens if t not in STOPWORDS]


@lru_cache(maxsize=1)
def _alias_groups() -> tuple:
    return tuple(tuple(tuple(tokenize(alias)) for alias in group) for group in SEARCH_SYNONYMS)


def _contains_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    return bool(phrase) and any(tuple(tokens[i:i + len(phrase)]) == phrase
                               for i in range(len(tokens) - len(phrase) + 1))


def query_tokens(query: str) -> list[str]:
    """Actual deduplicated query tokens, including the existing expansion."""
    words = tokenize(query)[:30]
    expanded = list(words)
    for group in _alias_groups():
        # Match token/phrase boundaries against the ORIGINAL query only: no
        # substring hits (fuel in refuelling) or cascading synonym expansion.
        if any(_contains_phrase(words, phrase) for phrase in group):
            expanded.extend(token for phrase in group for token in phrase)
    return list(dict.fromkeys(expanded))


def chunk_tokens(chunk: dict) -> list[str]:
    """Tokenize exactly the fields used by BM25, retaining term frequencies."""
    return tokenize(" ".join(str(chunk.get(key) or "") for key in _SEARCH_FIELDS))


def retrieve(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Return copies of matching chunks with a float `score`, highest first.

    Caller MUST filter scope, active revision/status and kind before calling:
    even IDF statistics must not depend on inaccessible documents. Equal scores
    retain input order. Scores may be zero/negative in small corpora and are not
    confidence probabilities. No corpus/index is cached across requests.
    """
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    terms = query_tokens(query)
    if not terms or not chunks:
        return []
    corpus = [chunk_tokens(chunk) for chunk in chunks]
    # BM25Okapi divides by vocabulary size/average length: an all-empty corpus
    # must not reach its constructor. Individual empty documents are supported.
    if not any(corpus):
        return []
    term_set = set(terms)
    matches = [i for i, tokens in enumerate(corpus) if not term_set.isdisjoint(tokens)]
    if not matches:
        return []
    scores = BM25Okapi(corpus).get_scores(terms)
    # Do not use score > 0 or get_top_n: the former loses genuine small-corpus
    # hits; the latter can include unrelated zero-score documents.
    matches.sort(key=lambda i: -float(scores[i]))
    return [{**chunks[i], "score": float(scores[i])} for i in matches[:top_k]]
