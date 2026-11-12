from __future__ import annotations

from collections.abc import Iterable

from .data.law_seed import LAW_SEED
from .models import LawArticle

EXPECTED_ARTICLE_COUNT = 108
EXPECTED_LAW_COUNT = 20


class CorpusError(ValueError):
    """Raised when the vendored corpus violates the expected contract."""


def load_articles(seed: Iterable[tuple[str, str, str, str]] = LAW_SEED) -> tuple[LawArticle, ...]:
    articles = tuple(
        LawArticle(
            law_name=law_name.strip(),
            article_no=article_no.strip(),
            text=text,
            keywords=tuple(item.strip() for item in keywords.split(",") if item.strip()),
        )
        for law_name, article_no, text, keywords in seed
    )
    _validate_articles(articles)
    return articles


def _validate_articles(articles: tuple[LawArticle, ...]) -> None:
    if len(articles) != EXPECTED_ARTICLE_COUNT:
        raise CorpusError(
            f"法条数量应为 {EXPECTED_ARTICLE_COUNT} 条，实际为 {len(articles)} 条"
        )
    if len({article.law_name for article in articles}) != EXPECTED_LAW_COUNT:
        raise CorpusError(f"法律数量应为 {EXPECTED_LAW_COUNT} 部")

    keys = [(article.law_name, article.article_no) for article in articles]
    if len(keys) != len(set(keys)):
        raise CorpusError("法条数据存在重复的（法律名, 条款号）")
    if any(not article.text for article in articles):
        raise CorpusError("法条正文不能为空")

