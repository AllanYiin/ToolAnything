"""Optional semantic retrieval building blocks for tool search."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from .metadata import normalize_metadata
from .models import ToolSpec
from .selection_strategies import RuleBasedStrategy, SelectionOptions


class OptionalDependencyNotAvailable(RuntimeError):
    """Raised when an optional semantic-search dependency is missing."""


class EmbeddingProvider(Protocol):
    """Encodes queries and tool documents into comparable vectors."""

    def encode_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        raise NotImplementedError

    def encode_queries(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        raise NotImplementedError


@dataclass(frozen=True)
class ToolSearchDocument:
    """A normalized text payload used for semantic indexing."""

    name: str
    text: str
    fingerprint: str


def _schema_type_name(definition: Mapping[str, Any]) -> str:
    raw_type = definition.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        return "/".join(str(item) for item in raw_type)

    variants = definition.get("oneOf")
    if isinstance(variants, list):
        variant_types = []
        for item in variants:
            if isinstance(item, Mapping):
                variant_type = item.get("type")
                if variant_type:
                    variant_types.append(str(variant_type))
        if variant_types:
            return "/".join(variant_types)

    return "any"


class ToolSearchDocumentBuilder:
    """Builds a multi-field text view from tool metadata and schema."""

    def __init__(
        self,
        *,
        include_description: bool = True,
        include_tags: bool = True,
        include_metadata: bool = True,
        include_parameters: bool = True,
    ) -> None:
        self.include_description = include_description
        self.include_tags = include_tags
        self.include_metadata = include_metadata
        self.include_parameters = include_parameters

    def build(self, spec: ToolSpec) -> ToolSearchDocument:
        metadata = normalize_metadata(spec.metadata, tags=spec.tags)
        payload: list[str] = [f"Tool name: {spec.name}"]

        if self.include_description and spec.description:
            payload.append(f"Description: {spec.description}")
        if self.include_tags and spec.tags:
            payload.append(f"Tags: {', '.join(spec.tags)}")
        if self.include_metadata:
            if metadata.category:
                payload.append(f"Category: {metadata.category}")
            if metadata.cost is not None:
                payload.append(f"Cost: {metadata.cost}")
            if metadata.latency_hint_ms is not None:
                payload.append(f"Latency hint ms: {metadata.latency_hint_ms}")
            if metadata.side_effect is not None:
                payload.append(f"Side effect: {metadata.side_effect}")
            if metadata.extra:
                payload.append(
                    "Extra metadata: "
                    + json.dumps(metadata.extra, ensure_ascii=False, sort_keys=True)
                )

        if self.include_parameters:
            payload.extend(self._format_parameters(spec.parameters))
        text = "\n".join(line for line in payload if line).strip()
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return ToolSearchDocument(name=spec.name, text=text, fingerprint=fingerprint)

    def _format_parameters(self, schema: Mapping[str, Any] | None) -> list[str]:
        if not isinstance(schema, Mapping):
            return []

        properties = schema.get("properties")
        if not isinstance(properties, Mapping) or not properties:
            return []

        required = {
            str(item)
            for item in schema.get("required", [])
            if isinstance(item, str)
        }
        lines = ["Parameters:"]
        for param_name, raw_definition in properties.items():
            if not isinstance(raw_definition, Mapping):
                continue

            type_name = _schema_type_name(raw_definition)
            flags = ["required" if param_name in required else "optional", f"type={type_name}"]
            description = raw_definition.get("description")
            if description:
                flags.append(f"description={description}")

            enum_values = raw_definition.get("enum")
            if isinstance(enum_values, list) and enum_values:
                flags.append(
                    "enum=" + ",".join(str(item) for item in enum_values)
                )

            default_value = raw_definition.get("default")
            if default_value is not None:
                flags.append(f"default={default_value}")

            lines.append(f"- {param_name}: {'; '.join(flags)}")

        return lines


class JinaOnnxEmbeddingsV5TextNanoRetrievalProvider:
    """Lazy-loaded ONNX Runtime wrapper for jinaai/jina-embeddings-v5-text-nano-retrieval."""

    def __init__(
        self,
        *,
        model_name: str = "jinaai/jina-embeddings-v5-text-nano-retrieval",
        query_prefix: str = "Query: ",
        document_prefix: str = "Document: ",
        onnx_subfolder: str = "onnx",
        onnx_filename: str = "model.onnx",
        dimensions: int | None = None,
        provider: str = "CPUExecutionProvider",
        trust_remote_code: bool = True,
        revision: str | None = None,
        cache_dir: str | None = None,
        module_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix
        self.onnx_subfolder = onnx_subfolder
        self.onnx_filename = onnx_filename
        self.dimensions = dimensions
        self.provider = provider
        self.trust_remote_code = trust_remote_code
        self.revision = revision
        self.cache_dir = cache_dir
        self._module_loader = module_loader or importlib.import_module
        self._tokenizer: Any | None = None
        self._session: Any | None = None
        self._numpy: Any | None = None

    def encode_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return self._encode(texts, prefix=self.document_prefix)

    def encode_queries(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return self._encode(texts, prefix=self.query_prefix)

    def _encode(self, texts: Sequence[str], *, prefix: str) -> list[tuple[float, ...]]:
        if not texts:
            return []

        tokenizer, session, np_module = self._load_components()
        prefixed = [f"{prefix}{text}" for text in texts]
        inputs = tokenizer(
            prefixed,
            padding=True,
            truncation=True,
            return_tensors="np",
        )

        ort_inputs = {}
        for input_meta in session.get_inputs():
            input_name = input_meta.name
            if input_name in inputs:
                ort_inputs[input_name] = inputs[input_name]

        if not ort_inputs:
            raise RuntimeError("ONNX embedding session received no compatible inputs.")

        outputs = session.run(None, ort_inputs)
        if not outputs:
            raise RuntimeError("ONNX embedding session returned no outputs.")

        last_hidden_state = outputs[0]
        attention_mask = inputs["attention_mask"]
        sequence_lengths = attention_mask.sum(axis=1) - 1
        batch_indices = np_module.arange(last_hidden_state.shape[0])
        pooled = last_hidden_state[batch_indices, sequence_lengths]
        pooled = self._l2_normalize(pooled, np_module)

        if self.dimensions is not None:
            pooled = pooled[:, : self.dimensions]

        return [tuple(float(value) for value in row) for row in pooled]

    def _l2_normalize(self, values: Any, np_module: Any) -> Any:
        norms = np_module.linalg.norm(values, axis=1, keepdims=True)
        norms = np_module.where(norms == 0, 1.0, norms)
        return values / norms

    def _load_components(self) -> tuple[Any, Any, Any]:
        if self._tokenizer is not None and self._session is not None and self._numpy is not None:
            return self._tokenizer, self._session, self._numpy

        try:
            transformers = self._module_loader("transformers")
            onnxruntime = self._module_loader("onnxruntime")
            np_module = self._module_loader("numpy")
            huggingface_hub = self._module_loader("huggingface_hub")
        except ImportError as exc:
            raise OptionalDependencyNotAvailable(
                "Semantic tool search with the ONNX retrieval backend requires the "
                "optional dependencies 'transformers', 'onnxruntime', 'numpy', and "
                "'huggingface-hub'. Install them only when needed."
            ) from exc

        tokenizer_cls = getattr(transformers, "AutoTokenizer", None)
        snapshot_download = getattr(huggingface_hub, "snapshot_download", None)
        inference_session_cls = getattr(onnxruntime, "InferenceSession", None)
        if tokenizer_cls is None or snapshot_download is None or inference_session_cls is None:
            raise OptionalDependencyNotAvailable(
                "Failed to import AutoTokenizer, snapshot_download, or InferenceSession "
                "for the ONNX retrieval backend."
            )

        model_dir = snapshot_download(
            repo_id=self.model_name,
            revision=self.revision,
            cache_dir=self.cache_dir,
            allow_patterns=[
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "config.json",
                "vocab.json",
                "merges.txt",
                "sentencepiece.bpe.model",
                "spiece.model",
                f"{self.onnx_subfolder}/{self.onnx_filename}",
            ],
        )
        onnx_path = Path(model_dir) / self.onnx_subfolder / self.onnx_filename
        self._tokenizer = tokenizer_cls.from_pretrained(
            model_dir,
            trust_remote_code=self.trust_remote_code,
        )
        self._session = inference_session_cls(str(onnx_path), providers=[self.provider])
        self._numpy = np_module
        return self._tokenizer, self._session, self._numpy


@dataclass
class _PreparedToolRecord:
    spec: ToolSpec
    document: ToolSearchDocument
    embedding: tuple[float, ...] | None = None


class SemanticToolIndex:
    """Caches tool documents and materializes embeddings on demand."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        document_builder: ToolSearchDocumentBuilder | None = None,
    ) -> None:
        self.provider = provider
        self.document_builder = document_builder or ToolSearchDocumentBuilder()
        self._records: dict[str, _PreparedToolRecord] = {}

    def on_tool_registered(self, spec: ToolSpec) -> None:
        self.prepare(spec)

    def on_tool_unregistered(self, name: str) -> None:
        self.remove(name)

    def prepare(self, spec: ToolSpec) -> None:
        document = self.document_builder.build(spec)
        current = self._records.get(spec.name)
        if current is not None and current.document.fingerprint == document.fingerprint:
            self._records[spec.name] = _PreparedToolRecord(
                spec=spec,
                document=current.document,
                embedding=current.embedding,
            )
            return

        self._records[spec.name] = _PreparedToolRecord(
            spec=spec,
            document=document,
            embedding=None,
        )

    def remove(self, name: str) -> None:
        self._records.pop(name, None)

    def ensure_synced(self, specs: Iterable[ToolSpec]) -> None:
        names = set()
        for spec in specs:
            names.add(spec.name)
            self.prepare(spec)

        stale_names = [name for name in self._records if name not in names]
        for name in stale_names:
            self.remove(name)

    def score(self, query: str, specs: Iterable[ToolSpec]) -> dict[str, float]:
        requested = list(specs)
        if not requested:
            return {}

        self.ensure_synced(requested)
        self._materialize_missing_embeddings()

        query_embeddings = self.provider.encode_queries([query])
        if not query_embeddings:
            return {}

        query_embedding = query_embeddings[0]
        scores: dict[str, float] = {}
        for spec in requested:
            record = self._records.get(spec.name)
            if record is None or record.embedding is None:
                continue
            scores[spec.name] = _cosine_similarity(query_embedding, record.embedding)

        return scores

    def _materialize_missing_embeddings(self) -> None:
        pending_names = [
            name for name, record in self._records.items() if record.embedding is None
        ]
        if not pending_names:
            return

        payloads = [self._records[name].document.text for name in pending_names]
        embeddings = self.provider.encode_documents(payloads)
        for name, embedding in zip(pending_names, embeddings):
            self._records[name].embedding = embedding


class SemanticRetrievalStrategy(RuleBasedStrategy):
    """Rule-based filters with semantic ranking over composed tool documents."""

    def __init__(
        self,
        index: SemanticToolIndex,
        *,
        semantic_weight: float = 1.0,
        lexical_weight: float = 0.15,
    ) -> None:
        self.index = index
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

    def select(
        self,
        tools: Iterable[ToolSpec],
        *,
        options: SelectionOptions,
        failure_score,
        now: float | None = None,
    ) -> list[ToolSpec]:
        specs = self._filter_by_tags(tools, options.tags)
        specs = self._filter_by_prefix(specs, options.prefix)
        specs = self._filter_by_metadata(
            specs,
            max_cost=options.max_cost,
            latency_budget_ms=options.latency_budget_ms,
            allow_side_effects=options.allow_side_effects,
            categories=options.categories,
        )

        if not options.query.strip():
            return super().select(
                specs,
                options=options,
                failure_score=failure_score,
                now=now,
            )

        semantic_scores = self.index.score(options.query, specs)
        if not semantic_scores:
            return super().select(
                specs,
                options=options,
                failure_score=failure_score,
                now=now,
            )

        scored = []
        for spec in specs:
            semantic_score = semantic_scores.get(spec.name, 0.0)
            lexical_score = self._similarity_score(options.query, spec)
            final_score = (
                semantic_score * self.semantic_weight
                + lexical_score * self.lexical_weight
            )
            failure = failure_score(spec.name, now=now)
            metadata = spec.normalized_metadata()
            cost_sort = metadata.cost if metadata.cost is not None else float("inf")
            latency_sort = (
                metadata.latency_hint_ms
                if metadata.latency_hint_ms is not None
                else float("inf")
            )
            scored.append(
                (
                    spec,
                    final_score,
                    semantic_score,
                    failure,
                    cost_sort,
                    latency_sort,
                )
            )

        if options.use_metadata_ranking:
            scored.sort(
                key=lambda item: (
                    -item[1],
                    -item[2],
                    item[3] if options.sort_by_failure else 0,
                    item[4],
                    item[5],
                    item[0].name,
                )
            )
        else:
            scored.sort(
                key=lambda item: (
                    -item[1],
                    -item[2],
                    item[3] if options.sort_by_failure else 0,
                    item[0].name,
                )
            )

        return [spec for spec, *_ in scored[: options.top_k]]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)
