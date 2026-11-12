from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class LawArticle:
    law_name: str
    article_no: str
    text: str
    keywords: tuple[str, ...]

    @property
    def article_id(self) -> str:
        return f"{self.law_name}-{self.article_no}"

    @property
    def source_url(self) -> str:
        return law_source_url(self.law_name)

    def as_dict(self) -> dict[str, object]:
        return {
            "law_name": self.law_name,
            "article_no": self.article_no,
            "text": self.text,
            "keywords": list(self.keywords),
            "source_url": self.source_url,
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    article: LawArticle
    score: float

    def as_dict(self) -> dict[str, object]:
        return {**self.article.as_dict(), "score": round(self.score, 6)}


def law_source_url(law_name: str) -> str:
    """Return the official search page for one law."""
    return f"https://flk.npc.gov.cn/search.html?keyword={quote(law_name, safe='')}"

