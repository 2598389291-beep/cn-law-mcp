from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .corpus import corpus_digest, load_articles
from .index import BM25Index, build_index

CACHE_VERSION = 1


@dataclass(frozen=True, slots=True)
class IndexLoadResult:
    index: BM25Index
    cache_hit: bool
    corpus_digest: str


def cache_directory() -> Path:
    override = os.environ.get("CN_LAW_MCP_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "cn-law-mcp"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "cn-law-mcp"
    return Path.home() / ".cache" / "cn-law-mcp"


def index_cache_path(digest: str) -> Path:
    return cache_directory() / f"bm25-index-v{CACHE_VERSION}-{digest[:16]}.json"


def load_or_build_index() -> IndexLoadResult:
    digest = corpus_digest()
    cache_path = index_cache_path(digest)
    cached = _read_cached_index(cache_path, digest)
    if cached is not None:
        return IndexLoadResult(index=cached, cache_hit=True, corpus_digest=digest)

    index = build_index(load_articles())
    _write_cached_index(cache_path, digest, index)
    return IndexLoadResult(index=index, cache_hit=False, corpus_digest=digest)


def _read_cached_index(path: Path, digest: str) -> BM25Index | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("version") != CACHE_VERSION
            or payload.get("corpus_digest") != digest
        ):
            return None
        articles = load_articles()
        term_frequencies = tuple(
            Counter(document) for document in payload["term_frequencies"]
        )
        document_lengths = tuple(payload["document_lengths"])
        if len(term_frequencies) != len(articles) or len(document_lengths) != len(articles):
            return None
        return BM25Index(
            articles=articles,
            term_frequencies=term_frequencies,
            document_lengths=document_lengths,
            idf={str(term): float(value) for term, value in payload["idf"].items()},
            average_document_length=float(payload["average_document_length"]),
            k1=float(payload["k1"]),
            b=float(payload["b"]),
            keyword_match_weight=float(payload["keyword_match_weight"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_cached_index(path: Path, digest: str, index: BM25Index) -> None:
    payload: dict[str, Any] = {
        "version": CACHE_VERSION,
        "corpus_digest": digest,
        "term_frequencies": [dict(counter) for counter in index.term_frequencies],
        "document_lengths": list(index.document_lengths),
        "idf": index.idf,
        "average_document_length": index.average_document_length,
        "k1": index.k1,
        "b": index.b,
        "keyword_match_weight": index.keyword_match_weight,
    }
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, separators=(",", ":"))
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            with contextlib.suppress(OSError):
                temporary_path.unlink(missing_ok=True)

