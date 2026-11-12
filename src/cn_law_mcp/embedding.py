from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class EmbeddingUnavailable(RuntimeError):
    """Raised when the optional embedding endpoint cannot serve a request."""


class TextEmbedder(Protocol):
    cache_key: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    url: str
    model: str
    api_key: str | None = None
    timeout: float = 8.0
    batch_size: int = 64

    @property
    def cache_key(self) -> str:
        raw = f"{self.url}\0{self.model}".encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    @classmethod
    def from_env(cls) -> EmbeddingConfig | None:
        url = os.environ.get("CN_LAW_MCP_EMBEDDING_URL", "").strip()
        model = os.environ.get("CN_LAW_MCP_EMBEDDING_MODEL", "").strip()
        if not url or not model:
            return None
        try:
            timeout = max(float(os.environ.get("CN_LAW_MCP_EMBEDDING_TIMEOUT", "8")), 0.5)
        except ValueError:
            timeout = 8.0
        return cls(
            url=url,
            model=model,
            api_key=os.environ.get("CN_LAW_MCP_EMBEDDING_API_KEY") or None,
            timeout=timeout,
        )


class OpenAICompatibleEmbedder:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self.cache_key = config.cache_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.config.batch_size):
            vectors.extend(self._embed_batch(texts[offset : offset + self.config.batch_size]))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json", "User-Agent": "cn-law-mcp"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            self.config.url,
            data=json.dumps(
                {"model": self.config.model, "input": texts},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise EmbeddingUnavailable("embedding 服务不可用") from exc

        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise EmbeddingUnavailable("embedding 服务返回格式不正确")
        rows = sorted(rows, key=lambda row: row.get("index", 0))
        vectors: list[list[float]] = []
        for row in rows:
            raw_vector = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(raw_vector, list) or not raw_vector:
                raise EmbeddingUnavailable("embedding 服务返回空向量")
            vector = [float(value) for value in raw_vector]
            if any(not math.isfinite(value) for value in vector):
                raise EmbeddingUnavailable("embedding 服务返回了非有限数值")
            vectors.append(vector)
        return vectors


def build_embedder_from_env() -> TextEmbedder | None:
    config = EmbeddingConfig.from_env()
    return OpenAICompatibleEmbedder(config) if config is not None else None

