from cn_law_mcp.corpus import load_articles
from cn_law_mcp.index import build_index


def test_bm25_finds_consumer_law_article_25():
    index = build_index(load_articles())
    hits = index.search("网购七天无理由退货是第几条", top_k=5)

    top = hits[0].article
    assert (top.law_name, top.article_no) == ("消费者权益保护法", "第25条")


def test_search_result_carries_required_fields():
    index = build_index(load_articles())
    result = index.search("外卖吃出异物", top_k=1)[0].as_dict()
    assert set(result) == {
        "law_name",
        "article_no",
        "text",
        "keywords",
        "source_url",
        "score",
    }

