import json

from cn_law_mcp.cache import index_cache_path, load_or_build_index


def test_index_is_reused_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CN_LAW_MCP_CACHE_DIR", str(tmp_path))

    first = load_or_build_index()
    second = load_or_build_index()

    assert not first.cache_hit
    assert second.cache_hit
    assert index_cache_path(first.corpus_digest).is_file()
    query = "网购七天无理由退货是第几条"
    assert first.index.search(query, 1)[0].article.article_no == "第25条"
    assert second.index.search(query, 1)[0].article.article_no == "第25条"


def test_corrupt_cache_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setenv("CN_LAW_MCP_CACHE_DIR", str(tmp_path))
    first = load_or_build_index()
    cache_path = index_cache_path(first.corpus_digest)
    cache_path.write_text(json.dumps({"version": "broken"}), encoding="utf-8")

    result = load_or_build_index()

    assert not result.cache_hit
    assert json.loads(cache_path.read_text(encoding="utf-8"))["version"] == 1

