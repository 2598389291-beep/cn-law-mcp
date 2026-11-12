from __future__ import annotations

import math
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .cache import load_or_build_index
from .corpus import corpus_digest
from .embedding import TextEmbedder, build_embedder_from_env
from .index import BM25Index
from .models import LawArticle, SearchHit
from .references import extract_citations, normalize_article_no

MAX_TOP_K = 50


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


class CitationItem(BaseModel):
    raw_text: str = Field(description="文本中的原始引用片段")
    law_name: str = Field(description="识别出的法律名称")
    article_no: str = Field(description="规范化后的条款号")
    exists: bool | None = Field(description="能否在本地白名单中确认；无法核验时为 null")
    status: Literal["verified", "not_found", "unverifiable"] = Field(
        description="核验状态"
    )
    message: str = Field(description="核验结论")
    article: ArticleResult | None = Field(default=None, description="已确认时的法条信息")


class CiteCheckSuccess(BaseModel):
    citations: list[CitationItem] = Field(description="逐条核验结果")
    citation_count: int = Field(description="识别出的引用数量")
    verified_count: int = Field(description="本地白名单已确认数量")
    not_found_count: int = Field(description="本地白名单未找到数量")
    unverifiable_count: int = Field(description="超出本地语料、无法核验数量")
    verification_scope: str = Field(description="本次核验覆盖范围")


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


class LawService:
    def __init__(
        self,
        index: BM25Index | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        if index is None:
            self.index = load_or_build_index().index
            self.corpus_digest = corpus_digest()
        else:
            self.index = index
            self.corpus_digest = corpus_digest()
        self.embedder = embedder if embedder is not None else build_embedder_from_env()
        self._embedding_lock = Lock()
        self._document_embeddings: list[list[float]] | None = None
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
            retrieval_mode = "字符 n-gram + BM25"
            hits = self.index.search(clean_query, top_k=top_k)
            if self.embedder is not None:
                hybrid = self._hybrid_search(clean_query, top_k)
                if hybrid is None:
                    retrieval_mode = "字符 n-gram + BM25（向量不可用，已降级）"
                else:
                    hits = hybrid
                    retrieval_mode = "字符 n-gram + BM25 + 向量"
            results = [_article_result(hit.article) for hit in hits]
            return SearchSuccess(
                query=clean_query,
                results=results,
                count=len(results),
                retrieval_mode=retrieval_mode,
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

    def cite_check(self, text: str) -> CiteCheckSuccess | ErrorResult:
        try:
            clean_text = text.strip()
            if not clean_text:
                return _error(
                    "待核验文本不能为空",
                    "请粘贴包含法条引用的文字，例如“《消费者权益保护法》第25条”",
                )

            known_laws = {article.law_name for article in self.index.articles}
            mentions = extract_citations(clean_text, known_laws)
            items: list[CitationItem] = []
            for mention in mentions:
                law_name = normalize_law_name(mention.law_name)
                article = self._by_key.get((law_name, mention.article_no))
                if article is not None:
                    items.append(
                        CitationItem(
                            raw_text=mention.raw_text,
                            law_name=law_name,
                            article_no=mention.article_no,
                            exists=True,
                            status="verified",
                            message="已在本地 108 条法条白名单中确认",
                            article=_article_result(article),
                        )
                    )
                elif law_name in known_laws:
                    items.append(
                        CitationItem(
                            raw_text=mention.raw_text,
                            law_name=law_name,
                            article_no=mention.article_no,
                            exists=False,
                            status="not_found",
                            message="该条不在本地 108 条法条白名单中，不能视为已核实引用",
                        )
                    )
                else:
                    items.append(
                        CitationItem(
                            raw_text=mention.raw_text,
                            law_name=law_name,
                            article_no=mention.article_no,
                            exists=None,
                            status="unverifiable",
                            message="该法律不在本地语料中，无法核验；请到官方数据库查询",
                        )
                    )

            return CiteCheckSuccess(
                citations=items,
                citation_count=len(items),
                verified_count=sum(item.status == "verified" for item in items),
                not_found_count=sum(item.status == "not_found" for item in items),
                unverifiable_count=sum(item.status == "unverifiable" for item in items),
                verification_scope="本地 108 条法条白名单；未覆盖全部现行法律法规",
            )
        except Exception:
            return _error(
                "法条引用核验暂时失败",
                "请稍后重试；也可以改用 search_law 或 get_article 单独核对",
            )

    def _hybrid_search(self, query: str, top_k: int) -> list[SearchHit] | None:
        assert self.embedder is not None
        try:
            document_embeddings = self._get_document_embeddings()
            query_embedding = self.embedder.embed([query])[0]
            vector_scores = [
                _cosine_similarity(query_embedding, document_embedding)
                for document_embedding in document_embeddings
            ]
            if not any(score > 0 for score in vector_scores):
                return None

            bm25_hits = self.index.search(query, top_k=len(self.index.articles))
            bm25_by_id = {hit.article.article_id: hit.score for hit in bm25_hits}
            max_bm25 = max(bm25_by_id.values(), default=0.0) or 1.0
            max_vector = max(vector_scores)
            combined = [
                (
                    0.5 * (bm25_by_id[article.article_id] / max_bm25)
                    + 0.5 * (vector_score / max_vector),
                    article,
                )
                for article, vector_score in zip(
                    self.index.articles, vector_scores, strict=True
                )
            ]
            combined.sort(
                key=lambda item: (
                    -item[0],
                    item[1].law_name,
                    item[1].article_no,
                )
            )
            return [
                SearchHit(article=article, score=score)
                for score, article in combined[:top_k]
            ]
        except Exception:
            return None

    def _get_document_embeddings(self) -> list[list[float]]:
        if self._document_embeddings is None:
            with self._embedding_lock:
                if self._document_embeddings is None:
                    assert self.embedder is not None
                    documents = [
                        (
                            f"{article.law_name} {article.article_no} "
                            f"{' '.join(article.keywords)} {article.text}"
                        )
                        for article in self.index.articles
                    ]
                    self._document_embeddings = self.embedder.embed(documents)
        return self._document_embeddings


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding 维度不一致")
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)

