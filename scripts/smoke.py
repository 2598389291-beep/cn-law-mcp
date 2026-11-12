from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    cache_directory = tempfile.mkdtemp(prefix="cn-law-mcp-smoke-")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["CN_LAW_MCP_CACHE_DIR"] = cache_directory
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cn_law_mcp"],
        cwd=ROOT,
        env=environment,
    )

    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        if tool_names != {"search_law", "get_article", "cite_check"}:
            raise RuntimeError(f"MCP tools 不符合预期: {sorted(tool_names)}")

        result = await session.call_tool(
            "search_law",
            {"query": "网购七天无理由退货是第几条", "top_k": 1},
        )
        payload = result.structured_content["result"]
        article = payload["results"][0]
        if (article["law_name"], article["article_no"]) != (
            "消费者权益保护法",
            "第25条",
        ):
            raise RuntimeError(f"检索结果不符合预期: {article}")
        if not article["source_url"].startswith("https://flk.npc.gov.cn/"):
            raise RuntimeError("检索结果缺少官方来源链接")

    print("smoke test passed: 消费者权益保护法 第25条")


if __name__ == "__main__":
    anyio.run(main)

