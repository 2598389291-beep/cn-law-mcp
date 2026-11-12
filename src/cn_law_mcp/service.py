from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from .corpus import load_articles
from .index import BM25Index, build_index
from .models import LawArticle

MAX_TOP_K = 50
_ARTICLE_PATTERN = re.compile(r"^第?(\d+)条?$")


class ErrorResult(BaseModel):
    error: str = Field(description="错误原因")
    hint: str = Field(description="下一步建议")


class ArticleResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    law_name: str = Field(description="法律名称")
    article_no: str = Field(description="条款号，例如“第25条”")
    text: str = Field(description="法条原文")
    keywords: list[str] = Field(description="检索关键词")
    source_url: str = Field(description="国家法律法规数据库官方检索链接")


class SearchSuccess(BaseModel):
    query: str = Field(description="原始查询")
    results: list[ArticleResult] = Field(description="按相关度排序的法条")
    count: int = Field(description="返回条数")
    retrieval_mode: str = Field(description="当前检索模式")


def _error(message: str, hint: str) -> ErrorResult:
    return ErrorResult(error=message, hint=hint)


def _article_result(article: LawArticle) -> ArticleResult:
    return ArticleResult(
        law_name=article.law_name,
        article_no=article.article_no,
        text=article.text,
        keywords=list(article.keywords),
        source_url=article.source_url,
    )


def normalize_law_name(value: str) -> str:
    return value.strip().strip("《》").replace(" ", "")


def normalize_article_no(value: str) -> str:
    compact = value.strip().replace(" ", "")
    match = _ARTICLE_PATTERN.fullmatch(compact)
    if match:
        return f"第{match.group(1)}条"
    return compact


class LawService:
    def __init__(self, index: BM25Index | None = None) -> None:
        self.index = index or build_index(load_articles())
        self._by_key = {
            (article.law_name, article.article_no): article for article in self.index.articles
        }

    def search_law(self, query: str, top_k: int = 5) -> SearchSuccess | ErrorResult:
        try:
            clean_query = query.strip()
            if not clean_query:
                return _error("查询不能为空", "请描述你遇到的法律问题，例如“网购七天无理由退货”")
            if not 1 <= top_k <= MAX_TOP_K:
                return _error(
                    f"top_k 必须在 1 到 {MAX_TOP_K} 之间",
                    "请把 top_k 调整为 1 到 50 之间的整数",
                )
            hits = self.index.search(clean_query, top_k=top_k)
            results = [_article_result(hit.article) for hit in hits]
            return SearchSuccess(
                query=clean_query,
                results=results,
                count=len(results),
                retrieval_mode="字符 n-gram + BM25",
            )
        except Exception:
            return _error(
                "检索暂时失败",
                "请稍后重试；若问题持续，运行 cn-law-mcp --selftest 检查本地索引",
            )

    def get_article(self, law_name: str, article_no: str) -> ArticleResult | ErrorResult:
        try:
            normalized_law = normalize_law_name(law_name)
            normalized_article = normalize_article_no(article_no)
            if not normalized_law or not normalized_article:
                return _error(
                    "法律名和条款号不能为空",
                    "请提供完整法律名与条款号，例如“消费者权益保护法”“第25条”",
                )
            article = self._by_key.get((normalized_law, normalized_article))
            if article is None:
                return _error(
                    f"未找到《{normalized_law}》{normalized_article}",
                    "请先用 search_law 确认法律名和条款号；本地索引只覆盖 108 条法条",
                )
            return _article_result(article)
        except Exception:
            return _error(
                "读取法条暂时失败",
                "请稍后重试；若问题持续，运行 cn-law-mcp --selftest 检查本地索引",
            )

