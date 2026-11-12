from __future__ import annotations

import argparse
import sys

from . import __version__
from .corpus import load_articles
from .index import build_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cn-law-mcp",
        description="中国法条检索 MCP 服务",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="加载本地法条索引并执行一次检索自检",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        articles = load_articles()
        index = build_index(articles)
        hits = index.search("网购七天无理由退货是第几条", top_k=1)
        if not hits or hits[0].article.law_name != "消费者权益保护法":
            print("自检失败：未召回《消费者权益保护法》", file=sys.stderr)
            return 1
        print(f"{len(articles)} 条法条索引加载成功")
        return 0
    from .server import run_stdio

    run_stdio()
    return 0



