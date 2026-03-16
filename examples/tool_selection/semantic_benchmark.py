"""Semantic tool retrieval benchmark with multilingual and case-specific tool support."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import unicodedata
from typing import Any

from .catalog_shared import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.models import ToolSpec
from toolanything.core.registry import ToolRegistry
from toolanything.core.semantic_search import (
    JinaOnnxEmbeddingsV5TextNanoRetrievalProvider,
    OptionalDependencyNotAvailable,
    SemanticRetrievalStrategy,
    SemanticToolIndex,
    ToolSearchDocument,
    ToolSearchDocumentBuilder,
)
from toolanything.core.tool_search import ToolSearchTool


@dataclass(frozen=True)
class BenchmarkTool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkCase:
    query: str
    expected: str
    query_lang: str
    tools: tuple[BenchmarkTool, ...] = ()


class BenchmarkDatasetAdapter:
    """Minimal dataset adapter interface for retrieval-style evaluation."""

    def load_cases(self, split: str) -> list[BenchmarkCase]:
        raise NotImplementedError


class SyntheticMultilingualDatasetAdapter(BenchmarkDatasetAdapter):
    """Local benchmark cases for mono-lingual and cross-lingual retrieval."""

    _cases = {
        "mixed": [
            BenchmarkCase(
                query="target_lang 是英文的文件內容轉換",
                expected="catalog.translate_quality",
                query_lang="zh",
            ),
            BenchmarkCase(
                query="realtime 短句即時轉換",
                expected="catalog.translate_fast",
                query_lang="zh",
            ),
            BenchmarkCase(
                query="依照 to、subject、body 欄位送出通知",
                expected="catalog.send_email",
                query_lang="zh",
            ),
            BenchmarkCase(
                query="根據 amount 和 rate 算出結果",
                expected="catalog.calculate_tax",
                query_lang="zh",
            ),
            BenchmarkCase(
                query="把長段文字縮成重點摘要",
                expected="catalog.summarize",
                query_lang="zh",
            ),
        ],
        "zh": [
            BenchmarkCase(query="高品質文件翻譯成英文", expected="catalog.translate_quality", query_lang="zh"),
            BenchmarkCase(query="即時短句翻譯", expected="catalog.translate_fast", query_lang="zh"),
            BenchmarkCase(query="寄送電子郵件通知", expected="catalog.send_email", query_lang="zh"),
            BenchmarkCase(query="試算稅額", expected="catalog.calculate_tax", query_lang="zh"),
            BenchmarkCase(query="摘要一段文字", expected="catalog.summarize", query_lang="zh"),
        ],
        "en": [
            BenchmarkCase(query="high quality document translation", expected="catalog.translate_quality", query_lang="en"),
            BenchmarkCase(query="fast realtime translation", expected="catalog.translate_fast", query_lang="en"),
            BenchmarkCase(query="send an email notification", expected="catalog.send_email", query_lang="en"),
            BenchmarkCase(query="calculate tax amount", expected="catalog.calculate_tax", query_lang="en"),
            BenchmarkCase(query="summarize a long text", expected="catalog.summarize", query_lang="en"),
        ],
        "cross-zh-en": [
            BenchmarkCase(query="高品質文件翻譯成英文", expected="catalog.translate_quality", query_lang="zh"),
            BenchmarkCase(query="即時短句翻譯", expected="catalog.translate_fast", query_lang="zh"),
            BenchmarkCase(query="寄送電子郵件通知", expected="catalog.send_email", query_lang="zh"),
            BenchmarkCase(query="試算稅額", expected="catalog.calculate_tax", query_lang="zh"),
            BenchmarkCase(query="摘要一段文字", expected="catalog.summarize", query_lang="zh"),
        ],
        "cross-en-zh": [
            BenchmarkCase(query="high quality document translation", expected="catalog.translate_quality", query_lang="en"),
            BenchmarkCase(query="fast realtime translation", expected="catalog.translate_fast", query_lang="en"),
            BenchmarkCase(query="send an email notification", expected="catalog.send_email", query_lang="en"),
            BenchmarkCase(query="calculate tax amount", expected="catalog.calculate_tax", query_lang="en"),
            BenchmarkCase(query="summarize a long text", expected="catalog.summarize", query_lang="en"),
        ],
    }

    def load_cases(self, split: str) -> list[BenchmarkCase]:
        if split not in self._cases:
            raise ValueError(f"Unknown synthetic split: {split}")
        return list(self._cases[split])


class JsonFileDatasetAdapter(BenchmarkDatasetAdapter):
    """Load retrieval cases from a local JSON or JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_cases(self, split: str) -> list[BenchmarkCase]:
        if not self.path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.path}")

        cases: list[BenchmarkCase] = []
        for payload in _load_dataset_rows(self.path):
            if split != "all" and payload.get("split", "all") != split:
                continue
            cases.append(
                BenchmarkCase(
                    query=str(payload["query"]),
                    expected=str(payload["expected"]),
                    query_lang=str(payload.get("query_lang", "unknown")),
                    tools=tuple(_parse_benchmark_tools(payload.get("tools", []))),
                )
            )
        return cases


JsonlDatasetAdapter = JsonFileDatasetAdapter


def _load_dataset_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl_rows(path)

    content = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _load_jsonl_rows(path)

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "examples"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported dataset payload in {path}")


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


class KeywordEmbeddingProvider:
    """Deterministic fallback backend for tests and quick local experiments."""

    KEYWORDS = (
        "翻譯",
        "translation",
        "translate",
        "文件",
        "document",
        "quality",
        "高品質",
        "fast",
        "即時",
        "realtime",
        "email",
        "電子郵件",
        "notify",
        "通知",
        "tax",
        "稅",
        "summary",
        "summarize",
        "摘要",
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
        lowered = normalize_text(text)
        return tuple(float(lowered.count(keyword.lower())) for keyword in self.KEYWORDS)


class LocalizedToolSearchDocumentBuilder(ToolSearchDocumentBuilder):
    """Build per-language retrieval documents for each tool."""

    def __init__(
        self,
        *,
        languages: tuple[str, ...],
        include_description: bool = True,
        include_tags: bool = True,
        include_metadata: bool = True,
        include_parameters: bool = True,
    ) -> None:
        super().__init__(
            include_description=include_description,
            include_tags=include_tags,
            include_metadata=include_metadata,
            include_parameters=include_parameters,
        )
        self.languages = languages

    def build_all(self, spec: ToolSpec) -> list[ToolSearchDocument]:
        documents: list[ToolSearchDocument] = []
        for language in self.languages:
            localized_spec = self._localize_spec(spec, language)
            document = super().build(localized_spec)
            documents.append(
                ToolSearchDocument(
                    name=document.name,
                    text=document.text,
                    fingerprint=document.fingerprint,
                    variant=language,
                )
            )
        return documents

    def _localize_spec(self, spec: ToolSpec, language: str) -> ToolSpec:
        metadata = dict(spec.metadata)
        translated = _TOOL_TRANSLATIONS.get(spec.name, {})

        if language == "zh":
            description = translated.get("description_zh", spec.description)
            tags = tuple(translated.get("tags_zh", spec.tags))
            localized_parameters = _localize_parameters(spec.parameters, translated.get("parameters_zh", {}))
            metadata["owner_language"] = "zh"
        elif language == "en":
            description = translated.get("description_en", spec.description)
            tags = tuple(translated.get("tags_en", spec.tags))
            localized_parameters = _localize_parameters(spec.parameters, translated.get("parameters_en", {}))
            metadata["owner_language"] = "en"
        else:
            raise ValueError(f"Unsupported tool document language: {language}")

        return ToolSpec(
            name=spec.name,
            description=description,
            parameters=localized_parameters,
            adapters=spec.adapters,
            tags=tags,
            strict=spec.strict,
            metadata=metadata,
            documentation=spec.documentation,
            source_type=spec.source_type,
            invoker_id=spec.invoker_id,
            func=spec.func,
            invoker=spec.invoker,
        )


_TOOL_TRANSLATIONS = {
    "catalog.summarize": {
        "description_zh": "摘要一段文字",
        "description_en": "Summarize a block of text",
        "tags_zh": ("文字", "摘要"),
        "tags_en": ("text", "summary"),
        "parameters_zh": {"text": "要摘要的文字"},
        "parameters_en": {"text": "Text to summarize"},
    },
    "catalog.translate_quality": {
        "description_zh": "高品質文件翻譯",
        "description_en": "High quality document translation",
        "tags_zh": ("文字", "翻譯", "文件"),
        "tags_en": ("text", "translate", "document"),
        "parameters_zh": {"text": "文件內容", "target_lang": "目標語言"},
        "parameters_en": {"text": "Document content", "target_lang": "Target language"},
    },
    "catalog.translate_fast": {
        "description_zh": "快速短句翻譯",
        "description_en": "Fast short-sentence translation",
        "tags_zh": ("文字", "翻譯", "即時"),
        "tags_en": ("text", "translate", "realtime"),
        "parameters_zh": {"text": "短句內容", "target_lang": "目標語言"},
        "parameters_en": {"text": "Short sentence", "target_lang": "Target language"},
    },
    "catalog.send_email": {
        "description_zh": "寄送電子郵件通知",
        "description_en": "Send an email notification",
        "tags_zh": ("通知", "電子郵件"),
        "tags_en": ("notify", "email"),
        "parameters_zh": {"to": "收件者", "subject": "標題", "body": "內文"},
        "parameters_en": {"to": "Recipient", "subject": "Subject", "body": "Email body"},
    },
    "catalog.calculate_tax": {
        "description_zh": "試算稅額",
        "description_en": "Estimate tax amount",
        "tags_zh": ("財務", "試算"),
        "tags_en": ("finance", "calc"),
        "parameters_zh": {"amount": "金額", "rate": "稅率"},
        "parameters_en": {"amount": "Amount", "rate": "Tax rate"},
    },
}

_QUERY_ALIASES = {
    "繁中": "中文",
    "寄信": "寄送電子郵件",
    "郵件": "電子郵件",
    "mail": "email",
    "e-mail": "email",
    "taxes": "tax",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    for source, target in _QUERY_ALIASES.items():
        normalized = normalized.replace(source, target)
    return normalized


def _parse_benchmark_tools(raw_tools: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[BenchmarkTool]:
    tools: list[BenchmarkTool] = []
    for item in raw_tools:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags", [])
        tools.append(
            BenchmarkTool(
                name=str(item["name"]),
                description=str(item.get("description", "")),
                parameters=dict(item.get("parameters", {})),
                tags=tuple(str(tag) for tag in tags) if isinstance(tags, (list, tuple)) else (),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return tools


def _build_case_registry(tools: tuple[BenchmarkTool, ...]) -> ToolRegistry:
    registry = ToolRegistry()

    def _noop_tool(**_kwargs):
        return None

    for tool in tools:
        registry.register(
            ToolSpec(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                adapters=None,
                tags=tool.tags,
                strict=False,
                metadata=tool.metadata,
                source_type="benchmark",
                invoker_id=tool.name,
                func=_noop_tool,
            )
        )
    return registry


def _localize_parameters(parameters: dict, descriptions: dict[str, str]) -> dict:
    localized = json.loads(json.dumps(parameters))
    properties = localized.get("properties", {})
    if not isinstance(properties, dict):
        return localized

    for parameter_name, description in descriptions.items():
        raw_definition = properties.get(parameter_name)
        if isinstance(raw_definition, dict):
            raw_definition["description"] = description
    return localized


def _build_document_builder(profile: str, *, tool_doc_langs: tuple[str, ...]) -> ToolSearchDocumentBuilder:
    kwargs = {}
    if profile == "name-only":
        kwargs = dict(
            include_description=False,
            include_tags=False,
            include_metadata=False,
            include_parameters=False,
        )
    elif profile == "name-description":
        kwargs = dict(
            include_description=True,
            include_tags=False,
            include_metadata=False,
            include_parameters=False,
        )
    elif profile != "full":
        raise ValueError(f"Unknown profile: {profile}")

    return LocalizedToolSearchDocumentBuilder(languages=tool_doc_langs, **kwargs)


def _build_provider(
    backend: str,
    *,
    model_name: str,
    dimensions: int | None,
    cache_dir: str | None,
):
    if backend == "fake":
        return KeywordEmbeddingProvider()
    if backend == "onnx":
        return JinaOnnxEmbeddingsV5TextNanoRetrievalProvider(
            model_name=model_name,
            dimensions=dimensions,
            cache_dir=cache_dir,
        )
    raise ValueError(f"Unknown backend: {backend}")


def _build_dataset_adapter(dataset: str, *, dataset_path: str | None = None) -> BenchmarkDatasetAdapter:
    if dataset == "synthetic":
        return SyntheticMultilingualDatasetAdapter()
    if dataset in {"json", "jsonl"}:
        if not dataset_path:
            raise ValueError("--dataset-path is required when dataset=json")
        return JsonFileDatasetAdapter(dataset_path)
    raise ValueError(f"Unknown dataset: {dataset}")


def _split_tool_doc_langs(raw: str) -> tuple[str, ...]:
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not items:
        raise ValueError("tool_doc_langs must include at least one language")
    invalid = [item for item in items if item not in {"en", "zh"}]
    if invalid:
        raise ValueError(f"Unsupported tool document languages: {', '.join(invalid)}")
    return items


def describe_documents(*, profile: str, tool_doc_langs: tuple[str, ...] = ("en", "zh")) -> str:
    registry = build_registry()
    builder = _build_document_builder(profile, tool_doc_langs=tool_doc_langs)
    lines = [f"profile={profile}", f"tool_doc_langs={','.join(tool_doc_langs)}", ""]
    for spec in registry.list():
        for document in builder.build_all(spec):
            lines.append(f"[{spec.name}::{document.variant}]")
            lines.append(document.text)
            lines.append("")
    return "\n".join(lines).rstrip()


def run_benchmark(
    *,
    backend: str,
    profile: str,
    top_k: int = 1,
    dataset: str = "synthetic",
    split: str = "mixed",
    dataset_path: str | None = None,
    tool_doc_langs: tuple[str, ...] = ("en", "zh"),
    model_name: str = "jinaai/jina-embeddings-v5-text-nano-retrieval",
    dimensions: int | None = None,
    cache_dir: str | None = None,
    lexical_weight: float = 0.0,
) -> str:
    builder = _build_document_builder(profile, tool_doc_langs=tool_doc_langs)
    provider = _build_provider(
        backend,
        model_name=model_name,
        dimensions=dimensions,
        cache_dir=cache_dir,
    )
    dataset_adapter = _build_dataset_adapter(dataset, dataset_path=dataset_path)
    cases = dataset_adapter.load_cases(split)

    hits = 0
    lines = [
        f"backend={backend}",
        f"profile={profile}",
        f"dataset={dataset}",
        f"split={split}",
        f"tool_doc_langs={','.join(tool_doc_langs)}",
        f"lexical_weight={lexical_weight}",
        f"top_k={top_k}",
        "",
    ]
    for case in cases:
        registry = _build_case_registry(case.tools) if case.tools else build_registry()
        strategy = SemanticRetrievalStrategy(
            SemanticToolIndex(provider, document_builder=builder),
            lexical_weight=lexical_weight,
        )
        searcher = ToolSearchTool(registry, FailureLogManager(), strategy=strategy)
        normalized_query = normalize_text(case.query)
        results = searcher.search(query=normalized_query, top_k=top_k, sort_by_failure=False)
        names = [spec.name for spec in results]
        matched = case.expected in names
        hits += int(matched)
        lines.append(
            f"[{case.query_lang}] {case.query} -> {', '.join(names) if names else '(empty)'} "
            f"| expected={case.expected} | hit={matched}"
        )

    precision = hits / len(cases) if cases else 0.0
    lines.extend(["", f"hit_rate={hits}/{len(cases)} ({precision:.2%})"])
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
    parser.add_argument(
        "--dataset",
        choices=["synthetic", "json", "jsonl"],
        default="synthetic",
        help="Benchmark source. Use json to evaluate a local BFCL-style export. Existing jsonl files are still accepted.",
    )
    parser.add_argument(
        "--split",
        default="mixed",
        help="Dataset split. For the synthetic dataset: mixed, zh, en, cross-zh-en, cross-en-zh.",
    )
    parser.add_argument("--dataset-path", default=None, help="Local JSON/JSONL file when dataset=json.")
    parser.add_argument(
        "--tool-doc-langs",
        default="en,zh",
        help="Comma-separated tool document languages to index, for example: en or en,zh.",
    )
    parser.add_argument(
        "--show-documents",
        action="store_true",
        help="Print the retrieval documents generated for the selected profile.",
    )
    parser.add_argument(
        "--model-name",
        default="jinaai/jina-embeddings-v5-text-nano-retrieval",
        help="Hugging Face model id used when backend=onnx.",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Optional embedding dimension truncation for the ONNX backend.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional Hugging Face cache directory for the ONNX backend.",
    )
    parser.add_argument(
        "--lexical-weight",
        type=float,
        default=0.0,
        help="Blend weight for the legacy lexical similarity score. Use 0 to measure pure semantic retrieval.",
    )
    args = parser.parse_args()
    tool_doc_langs = _split_tool_doc_langs(args.tool_doc_langs)

    if args.show_documents:
        print(describe_documents(profile=args.profile, tool_doc_langs=tool_doc_langs))
        print()

    try:
        print(
            run_benchmark(
                backend=args.backend,
                profile=args.profile,
                top_k=args.top_k,
                dataset=args.dataset,
                split=args.split,
                dataset_path=args.dataset_path,
                tool_doc_langs=tool_doc_langs,
                model_name=args.model_name,
                dimensions=args.dimensions,
                cache_dir=args.cache_dir,
                lexical_weight=args.lexical_weight,
            )
        )
    except OptionalDependencyNotAvailable as exc:
        raise SystemExit(
            f"{exc}\n"
            "Install optional packages when needed, for example:\n"
            "python -m pip install onnxruntime transformers huggingface-hub numpy"
        ) from exc


if __name__ == "__main__":
    main()
