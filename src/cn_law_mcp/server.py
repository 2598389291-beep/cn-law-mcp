from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from . import __version__
from .service import (
    ArticleResult,
    CiteCheckSuccess,
    ErrorResult,
    LawService,
    SearchSuccess,
)

SERVER_NAME = "cn-law-mcp"
SERVER_INSTRUCTIONS = (
    "中国法条检索服务。用户询问具体法律条文、消费维权依据、退款退货或赔偿责任时，"
    "应先调用 search_law 获取候选条文；已知法律名和条款号时调用 get_article。"
    "回答必须保留工具返回的原文和 source_url，不得自行补写法条。"
)


def build_server(service: LawService | None = None) -> MCPServer[Any]:
    law_service = service or LawService()
    server = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.tool(
        name="search_law",
        description=(
            "检索与用户问题最相关的中国法条。适合在需要法律依据、退款退货规则、"
            "赔偿标准或平台责任时调用。返回法律名称、条款号、原文、关键词和官方链接。"
        ),
    )
    def search_law(
        query: Annotated[
            str,
            Field(description="用户的原始问题，用大白话即可，例如“网购七天无理由退货是第几条”"),
        ],
        top_k: Annotated[
            int,
            Field(default=5, description="返回条数，建议 1-10，最多 50"),
        ] = 5,
    ) -> SearchSuccess | ErrorResult:
        return law_service.search_law(query, top_k)

    @server.tool(
        name="get_article",
        description=(
            "按法律名和条款号精确读取一条中国法条。仅在已经知道准确法律名和条号时调用；"
            "如果不确定名称或条号，先调用 search_law。"
        ),
    )
    def get_article(
        law_name: Annotated[
            str,
            Field(description="完整法律名称，例如“消费者权益保护法”"),
        ],
        article_no: Annotated[
            str,
            Field(description="条款号，例如“第25条”或“25”"),
        ],
    ) -> ArticleResult | ErrorResult:
        return law_service.get_article(law_name, article_no)

    @server.tool(
        name="cite_check",
        description=(
            "抽取一段文字中的中国法条引用，并逐条核对本地 108 条法条白名单。"
            "适合在模型准备给出法律依据、或用户要求验证法条真伪时调用。"
            "返回 verified、not_found 或 unverifiable，不要把 unverifiable 当作真实引用。"
        ),
    )
    def cite_check(
        text: Annotated[
            str,
            Field(description="需要核验的完整文字，其中应包含法律名和条款号"),
        ],
    ) -> CiteCheckSuccess | ErrorResult:
        return law_service.cite_check(text)

    return server


def run_stdio() -> None:
    build_server().run("stdio")

