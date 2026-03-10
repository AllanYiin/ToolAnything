"""Semantic tool retrieval benchmark for comparing document encodings."""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from .catalog_shared import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.semantic_search import (
    JinaOnnxEmbeddingsV5TextNanoRetrievalProvider,
    SemanticRetrievalStrategy,
    SemanticToolIndex,
    ToolSearchDocumentBuilder,
)
from toolanything.core.tool_search import ToolSearchTool


@dataclass(frozen=True)
class BenchmarkCase:
    query: str
    expected: str


CASES = [
    BenchmarkCase(query="target_lang 是英文的文件內容轉換", expected="catalog.translate_quality"),
    BenchmarkCase(query="realtime 短句即時轉換", expected="catalog.translate_fast"),
    BenchmarkCase(query="依照 to、subject、body 欄位送出通知", expected="catalog.send_email"),
    BenchmarkCase(query="根據 amount 和 rate 算出結果", expected="catalog.calculate_tax"),
    BenchmarkCase(query="把長段文字縮成重點摘要", expected="catalog.summarize"),
]


class KeywordEmbeddingProvider:
    """Deterministic fallback backend for tests and quick local experiments."""

    KEYWORDS = (
        "翻譯",
        "translate",
        "quality",
        "fast",
        "email",
        "通知",
        "tax",
        "稅",
        "摘要",
        "summary",
        "subject",
        "body",
        "target_lang",
        "amount",
        "rate",
    )

    def encode_documents(self, texts):
        return [self._encode(text) for text in texts]

    def encode_queries(self, texts):
        return [self._encode(text) for text in texts]

    def _encode(self, text: str) -> tuple[float, ...]:
        lowered = text.lower()
        return tuple(float(lowered.count(keyword.lower())) for keyword in self.KEYWORDS)


def _build_document_builder(profile: str) -> ToolSearchDocumentBuilder:
    if profile == "name-only":
        return ToolSearchDocumentBuilder(
            include_description=False,
            include_tags=False,
            include_metadata=False,
            include_parameters=False,
        )
    if profile == "name-description":
        return ToolSearchDocumentBuilder(
            include_description=True,
            include_tags=False,
            include_metadata=False,
            include_parameters=False,
        )
    if profile == "full":
        return ToolSearchDocumentBuilder()
    raise ValueError(f"Unknown profile: {profile}")


def _build_provider(backend: str):
    if backend == "fake":
        return KeywordEmbeddingProvider()
    if backend == "onnx":
        return JinaOnnxEmbeddingsV5TextNanoRetrievalProvider()
    raise ValueError(f"Unknown backend: {backend}")


def run_benchmark(*, backend: str, profile: str, top_k: int = 1) -> str:
    registry = build_registry()
    builder = _build_document_builder(profile)
    provider = _build_provider(backend)
    strategy = SemanticRetrievalStrategy(
        SemanticToolIndex(provider, document_builder=builder)
    )
    searcher = ToolSearchTool(registry, FailureLogManager(), strategy=strategy)

    hits = 0
    lines = [
        f"backend={backend}",
        f"profile={profile}",
        f"top_k={top_k}",
        "",
    ]
    for case in CASES:
        results = searcher.search(query=case.query, top_k=top_k, sort_by_failure=False)
        names = [spec.name for spec in results]
        matched = case.expected in names
        hits += int(matched)
        lines.append(
            f"{case.query} -> {', '.join(names) if names else '(empty)'} | expected={case.expected} | hit={matched}"
        )

    precision = hits / len(CASES)
    lines.extend(["", f"hit_rate={hits}/{len(CASES)} ({precision:.2%})"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark semantic tool retrieval profiles.")
    parser.add_argument(
        "--backend",
        choices=["fake", "onnx"],
        default="fake",
        help="Embedding backend. 'onnx' requires optional packages and the Jina retrieval model.",
    )
    parser.add_argument(
        "--profile",
        choices=["name-only", "name-description", "full"],
        default="full",
        help="How much tool information is encoded into the retrieval document.",
    )
    parser.add_argument("--top-k", type=int, default=1)
    args = parser.parse_args()

    print(run_benchmark(backend=args.backend, profile=args.profile, top_k=args.top_k))


if __name__ == "__main__":
    main()
