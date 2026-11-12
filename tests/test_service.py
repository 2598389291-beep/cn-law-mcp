from cn_law_mcp.service import ErrorResult, LawService


def test_search_returns_five_required_fields():
    service = LawService()
    result = service.search_law("网购七天无理由退货是第几条", top_k=5)
    assert not isinstance(result, ErrorResult)
    assert result.count == 5
    top = result.results[0]
    assert (top.law_name, top.article_no) == ("消费者权益保护法", "第25条")
    assert top.text
    assert top.keywords
    assert top.source_url.startswith("https://flk.npc.gov.cn/")


def test_get_article_accepts_plain_arabic_article_number():
    service = LawService()
    result = service.get_article("《消费者权益保护法》", "25")
    assert not isinstance(result, ErrorResult)
    assert result.article_no == "第25条"
    assert result.keywords == ["网购", "七天无理由", "退货"]


def test_get_article_returns_structured_not_found_error():
    result = LawService().get_article("消费者权益保护法", "第999条")
    assert isinstance(result, ErrorResult)
    assert set(result.model_dump()) == {"error", "hint"}
    assert "未找到" in result.error


def test_search_validates_top_k_without_raising():
    result = LawService().search_law("退货", top_k=0)
    assert isinstance(result, ErrorResult)
    assert "top_k" in result.error

