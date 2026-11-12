import asyncio

from cn_law_mcp.server import build_server


def test_mcp_exposes_search_and_get_article_with_chinese_descriptions():
    tools = asyncio.run(build_server().list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {"search_law", "get_article", "cite_check"}
    assert "检索" in by_name["search_law"].description
    assert "精确读取" in by_name["get_article"].description
    assert "逐条核对" in by_name["cite_check"].description
    assert "用户的原始问题" in by_name["search_law"].input_schema["properties"]["query"][
        "description"
    ]
    assert "完整法律名称" in by_name["get_article"].input_schema["properties"]["law_name"][
        "description"
    ]
    assert "需要核验的完整文字" in by_name["cite_check"].input_schema["properties"]["text"][
        "description"
    ]


def test_mcp_tool_call_returns_structured_content():
    result = asyncio.run(
        build_server().call_tool(
            "search_law",
            {"query": "网购七天无理由退货是第几条", "top_k": 1},
        )
    )
    payload = result.structured_content["result"]
    assert payload["results"][0]["law_name"] == "消费者权益保护法"
    assert payload["results"][0]["article_no"] == "第25条"

