import hashlib
from pathlib import Path

import cn_law_mcp.data.law_seed as law_seed_module
from cn_law_mcp.corpus import load_articles

SOURCE_SHA256 = "21ed5fc613b203a6856941013775ed0d7c97bc5112a649e53d423c21f3b5bd6f"


def test_vendored_seed_is_byte_for_byte_copy():
    source = Path(law_seed_module.__file__).read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256


def test_corpus_contract_and_official_links():
    articles = load_articles()
    assert len(articles) == 108
    assert len({article.law_name for article in articles}) == 20
    assert all(article.source_url.startswith("https://flk.npc.gov.cn/") for article in articles)


def test_seven_day_return_article_text_is_unchanged():
    articles = load_articles()
    article = next(
        item
        for item in articles
        if item.law_name == "消费者权益保护法" and item.article_no == "第25条"
    )
    assert article.text == (
        "经营者采用网络、电视、电话、邮购等方式销售商品，"
        "消费者有权自收到商品之日起七日内退货，且无需说明理由。"
    )
    assert article.keywords == ("网购", "七天无理由", "退货")

