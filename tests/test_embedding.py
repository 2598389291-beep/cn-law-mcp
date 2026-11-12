from cn_law_mcp.corpus import load_articles
from cn_law_mcp.embedding import EmbeddingConfig
from cn_law_mcp.index import build_index
from cn_law_mcp.service import ErrorResult, LawService


class FakeEmbedder:
    cache_key = "fake"

    def embed(self, texts: list[str]):
        vectors = []
        for text in texts:
            if text.startswith("消费者权益保护法 第25条") or "无理由退货是第几条" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors


class BrokenEmbedder:
    cache_key = "broken"

    def embed(self, texts: list[str]):
        raise RuntimeError("offline")


def test_embedding_config_requires_url_and_model(monkeypatch):
    monkeypatch.delenv("CN_LAW_MCP_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("CN_LAW_MCP_EMBEDDING_MODEL", raising=False)
    assert EmbeddingConfig.from_env() is None

    monkeypatch.setenv("CN_LAW_MCP_EMBEDDING_URL", "http://127.0.0.1:8000/v1/embeddings")
    monkeypatch.setenv("CN_LAW_MCP_EMBEDDING_MODEL", "local-model")
    config = EmbeddingConfig.from_env()
    assert config is not None
    assert config.api_key is None


def test_optional_embedding_enables_hybrid_search():
    service = LawService(index=build_index(load_articles()), embedder=FakeEmbedder())
    result = service.search_law("无理由退货是第几条", top_k=3)
    assert not isinstance(result, ErrorResult)
    assert "向量" in result.retrieval_mode
    assert result.results[0].article_no == "第25条"


def test_embedding_failure_falls_back_to_bm25():
    service = LawService(index=build_index(load_articles()), embedder=BrokenEmbedder())
    result = service.search_law("网购七天无理由退货是第几条", top_k=1)
    assert not isinstance(result, ErrorResult)
    assert "降级" in result.retrieval_mode
    assert result.results[0].article_no == "第25条"

