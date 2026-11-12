from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .models import LawArticle, SearchHit

_CLEAN_RE = re.compile(r"[^\w\u3400-\u4dbf\u4e00-\u9fff]+", re.UNICODE)


def _normalize(text: str) -> str:
    return _CLEAN_RE.sub("", text.lower())


def tokenize(text: str) -> list[str]:
    normalized = _normalize(text)
    return [
        normalized[index : index + size]
        for size in (2, 3)
        for index in range(max(len(normalized) - size + 1, 0))
        if len(normalized[index : index + size]) == size
    ]


def _weighted_document(article: LawArticle) -> list[str]:
    tokens: list[str] = []
    tokens.extend(tokenize(article.law_name) * 3)
    tokens.extend(tokenize(article.article_no) * 4)
    for keyword in article.keywords:
        tokens.extend(tokenize(keyword) * 2)
    tokens.extend(tokenize(article.text))
    return tokens


@dataclass(frozen=True, slots=True)
class BM25Index:
    articles: tuple[LawArticle, ...]
    term_frequencies: tuple[Counter[str], ...]
    document_lengths: tuple[int, ...]
    idf: dict[str, float]
    average_document_length: float
    k1: float = 1.5
    b: float = 0.75
    keyword_match_weight: float = 20.0

    @classmethod
    def build(
        cls,
        articles: tuple[LawArticle, ...],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        keyword_match_weight: float = 20.0,
    ) -> BM25Index:
        term_frequencies = tuple(Counter(_weighted_document(article)) for article in articles)
        document_lengths = tuple(sum(counter.values()) for counter in term_frequencies)
        document_count = len(articles)
        average_document_length = (
            sum(document_lengths) / document_count if document_count else 0.0
        )

        document_frequencies: Counter[str] = Counter()
        for counter in term_frequencies:
            document_frequencies.update(counter.keys())
        idf = {
            term: math.log(
                1.0
                + (document_count - frequency + 0.5)
                / (frequency + 0.5)
            )
            for term, frequency in document_frequencies.items()
        }
        return cls(
            articles=articles,
            term_frequencies=term_frequencies,
            document_lengths=document_lengths,
            idf=idf,
            average_document_length=average_document_length,
            k1=k1,
            b=b,
            keyword_match_weight=keyword_match_weight,
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        normalized_query = _normalize(query)
        query_terms = set(tokenize(normalized_query))
        if not query_terms or not self.articles:
            return []

        scored: list[SearchHit] = []
        for article, frequencies, document_length in zip(
            self.articles,
            self.term_frequencies,
            self.document_lengths,
            strict=True,
        ):
            score = 0.0
            length_ratio = (
                document_length / self.average_document_length
                if self.average_document_length
                else 0.0
            )
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * length_ratio)
                score += self.idf[term] * (frequency * (self.k1 + 1.0)) / denominator
            score += self.keyword_match_weight * sum(
                _normalize(keyword) in normalized_query for keyword in article.keywords
            )
            scored.append(SearchHit(article=article, score=score))

        scored.sort(
            key=lambda hit: (
                -hit.score,
                hit.article.law_name,
                hit.article.article_no,
            )
        )
        return scored[:top_k]


def build_index(articles: tuple[LawArticle, ...]) -> BM25Index:
    return BM25Index.build(articles)

