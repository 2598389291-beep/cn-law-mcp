from cn_law_mcp.references import extract_citations, parse_article_number


def test_parse_arabic_and_chinese_article_numbers():
    assert parse_article_number("第25条") == 25
    assert parse_article_number("二十五") == 25
    assert parse_article_number("第一百四十八") == 148
    assert parse_article_number("第五百七十七") == 577
    assert parse_article_number("第一千一百六十五") == 1165


def test_extract_multiple_references_from_bracketed_and_bare_names():
    text = (
        "依据《消费者权益保护法》第二十五条、第二十六条，"
        "以及民法典第五百七十七条，经营者应当承担责任。"
    )
    mentions = extract_citations(text, {"消费者权益保护法", "民法典"})
    assert [(item.law_name, item.article_no) for item in mentions] == [
        ("消费者权益保护法", "第25条"),
        ("消费者权益保护法", "第26条"),
        ("民法典", "第577条"),
    ]
