from __future__ import annotations

import re
from dataclasses import dataclass

_ARTICLE_TOKEN_RE = re.compile(r"第[0-9一二两三四五六七八九十百千零〇]+条")
_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


@dataclass(frozen=True, slots=True)
class CitationMention:
    raw_text: str
    law_name: str
    article_no: str
    position: int


def parse_article_number(value: str) -> int | None:
    compact = value.strip().replace(" ", "")
    compact = compact.removeprefix("第").removesuffix("条")
    if not compact:
        return None
    if compact.isdigit():
        return int(compact)

    total = 0
    current = 0
    for character in compact:
        if character in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[character]
            continue
        unit = _CHINESE_UNITS.get(character)
        if unit is None:
            return None
        total += (current or 1) * unit
        current = 0
    number = total + current
    return number or None


def normalize_article_no(value: str) -> str:
    number = parse_article_number(value)
    return f"第{number}条" if number is not None else value.strip().replace(" ", "")


def extract_citations(text: str, known_laws: set[str]) -> list[CitationMention]:
    mentions: list[CitationMention] = []
    occupied_spans: list[tuple[int, int]] = []

    bracketed = re.compile(
        rf"《(?P<law>[^》\n]{{1,60}})》\s*(?P<articles>{_ARTICLE_TOKEN_RE.pattern}"
        rf"(?:\s*[、,，和及]\s*{_ARTICLE_TOKEN_RE.pattern})*)"
    )
    for match in bracketed.finditer(text):
        law_name = match.group("law").strip()
        occupied_spans.append(match.span())
        for article_match in _ARTICLE_TOKEN_RE.finditer(match.group("articles")):
            mentions.append(
                CitationMention(
                    raw_text=f"《{law_name}》{article_match.group(0)}",
                    law_name=law_name,
                    article_no=normalize_article_no(article_match.group(0)),
                    position=match.start("articles") + article_match.start(),
                )
            )

    if not known_laws:
        return mentions

    law_pattern = "|".join(
        re.escape(law_name) for law_name in sorted(known_laws, key=len, reverse=True)
    )
    bare = re.compile(
        rf"(?P<law>{law_pattern})\s*(?P<articles>{_ARTICLE_TOKEN_RE.pattern}"
        rf"(?:\s*[、,，和及]\s*{_ARTICLE_TOKEN_RE.pattern})*)"
    )
    for match in bare.finditer(text):
        if any(start <= match.start() < end for start, end in occupied_spans):
            continue
        law_name = match.group("law")
        for article_match in _ARTICLE_TOKEN_RE.finditer(match.group("articles")):
            mentions.append(
                CitationMention(
                    raw_text=f"{law_name}{article_match.group(0)}",
                    law_name=law_name,
                    article_no=normalize_article_no(article_match.group(0)),
                    position=match.start("articles") + article_match.start(),
                )
            )

    mentions.sort(key=lambda mention: mention.position)
    return mentions

