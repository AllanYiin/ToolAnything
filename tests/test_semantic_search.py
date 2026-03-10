from __future__ import annotations

from dataclasses import dataclass

from toolanything.core import FailureLogManager, ToolRegistry, ToolSearchTool
from toolanything.core.models import ToolSpec
from toolanything.core.semantic_search import (
    JinaOnnxEmbeddingsV5TextNanoRetrievalProvider,
    OptionalDependencyNotAvailable,
    SemanticRetrievalStrategy,
    SemanticToolIndex,
    ToolSearchDocumentBuilder,
)


def _email_action(to: str, subject: str, body: str) -> dict:
    return {"to": to, "subject": subject, "body": body}


def _tax_action(amount: float, rate: float = 0.05) -> float:
    return amount * rate


class KeywordEmbeddingProvider:
    def __init__(self) -> None:
        self.document_calls = 0
        self.query_calls = 0
        self.keywords = (
            "subject",
            "body",
            "to",
            "amount",
            "rate",
            "email",
            "tax",
        )

    def encode_documents(self, texts):
        self.document_calls += 1
        return [self._encode(text) for text in texts]

    def encode_queries(self, texts):
        self.query_calls += 1
        return [self._encode(text) for text in texts]

    def _encode(self, text: str) -> tuple[float, ...]:
        lowered = text.lower()
        return tuple(float(lowered.count(keyword)) for keyword in self.keywords)


def test_document_builder_includes_metadata_and_parameters():
    spec = ToolSpec.from_function(
        _email_action,
        name="notify.email",
        description="寄送通知",
        metadata={"category": "ops", "side_effect": True, "owner": "system"},
    )

    document = ToolSearchDocumentBuilder().build(spec)
    assert "Tool name: notify.email" in document.text
    assert "Description: 寄送通知" in document.text
    assert "Category: ops" in document.text
    assert "Side effect: True" in document.text
    assert '"owner": "system"' in document.text
    assert "- to: required; type=string" in document.text
    assert "- subject: required; type=string" in document.text
    assert "- body: required; type=string" in document.text


def test_semantic_index_prepares_on_register_but_only_embeds_on_search():
    registry = ToolRegistry()
    provider = KeywordEmbeddingProvider()
    index = SemanticToolIndex(provider)
    registry.add_observer(index)

    registry.register(
        ToolSpec.from_function(
            _email_action,
            name="notify.email",
            description="寄送通知",
        )
    )

    assert provider.document_calls == 0

    scores = index.score("subject body to", registry.list())
    assert provider.document_calls == 1
    assert provider.query_calls == 1
    assert scores["notify.email"] > 0.0


def test_semantic_strategy_can_rank_by_parameter_shape():
    registry = ToolRegistry()
    registry.register(
        ToolSpec.from_function(
            _email_action,
            name="notify.email",
            description="執行任務",
            metadata={"category": "ops", "side_effect": True},
        )
    )
    registry.register(
        ToolSpec.from_function(
            _tax_action,
            name="finance.tax",
            description="執行任務",
            metadata={"category": "finance", "side_effect": False},
        )
    )

    strategy = SemanticRetrievalStrategy(SemanticToolIndex(KeywordEmbeddingProvider()))
    searcher = ToolSearchTool(registry, FailureLogManager(), strategy=strategy)

    results = searcher.search(query="subject body to", top_k=1, sort_by_failure=False)
    assert [spec.name for spec in results] == ["notify.email"]


def test_jina_onnx_provider_imports_modules_only_when_used():
    calls: list[str] = []

    class FakeTokenizer:
        def __call__(self, texts, padding=True, truncation=True, return_tensors="np"):
            assert padding is True
            assert truncation is True
            assert return_tensors == "np"
            return {
                "input_ids": [[1, 2], [1, 2]],
                "attention_mask": FakeArray([[1, 1], [1, 1]]),
            }

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return FakeTokenizer()

    class FakeInputMeta:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeSession:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get_inputs(self):
            return [FakeInputMeta("input_ids"), FakeInputMeta("attention_mask")]

        def run(self, _outputs, ort_inputs):
            assert "input_ids" in ort_inputs
            assert "attention_mask" in ort_inputs
            return [
                FakeArray(
                    [
                        [[0.0, 0.0], [3.0, 4.0]],
                        [[0.0, 0.0], [5.0, 12.0]],
                    ]
                )
            ]

    class FakeOnnxRuntime:
        InferenceSession = FakeSession

    class FakeHub:
        @staticmethod
        def snapshot_download(**kwargs):
            return "D:/fake-model"

    class FakeTransformers:
        AutoTokenizer = FakeAutoTokenizer

    class FakeNumpy:
        @staticmethod
        def arange(stop):
            return list(range(stop))

        class linalg:
            @staticmethod
            def norm(values, axis=1, keepdims=True):
                rows = []
                for row in values.rows:
                    magnitude = sum(item * item for item in row) ** 0.5
                    rows.append([magnitude] if keepdims else magnitude)
                return FakeArray(rows)

        @staticmethod
        def where(mask, when_true, when_false):
            rows = []
            for mask_row, false_row in zip(mask.rows, when_false.rows):
                rows.append(
                    [
                        when_true if item else false_item
                        for item, false_item in zip(mask_row, false_row)
                    ]
                )
            return FakeArray(rows)

    def loader(module_name: str):
        calls.append(module_name)
        mapping = {
            "transformers": FakeTransformers(),
            "onnxruntime": FakeOnnxRuntime(),
            "numpy": FakeNumpy(),
            "huggingface_hub": FakeHub(),
        }
        return mapping[module_name]

    provider = JinaOnnxEmbeddingsV5TextNanoRetrievalProvider(module_loader=loader)
    assert calls == []

    result = provider.encode_queries(["find email tool", "find tax tool"])
    assert calls == ["transformers", "onnxruntime", "numpy", "huggingface_hub"]
    assert result == [(0.6, 0.8), (0.38461538461538464, 0.9230769230769231)]


def test_jina_onnx_provider_raises_clear_error_when_optional_dependency_missing():
    provider = JinaOnnxEmbeddingsV5TextNanoRetrievalProvider(
        module_loader=lambda _name: (_ for _ in ()).throw(ImportError("missing"))
    )

    try:
        provider.encode_queries(["translate this"])
    except OptionalDependencyNotAvailable as exc:
        assert "onnxruntime" in str(exc)
    else:
        raise AssertionError("expected OptionalDependencyNotAvailable")


@dataclass
class FakeArray:
    rows: list

    @property
    def shape(self):
        first = self.rows[0]
        if isinstance(first, list) and first and isinstance(first[0], list):
            return (len(self.rows), len(first), len(first[0]))
        if isinstance(first, list):
            return (len(self.rows), len(first))
        return (len(self.rows),)

    def sum(self, axis=None):
        if axis != 1:
            raise AssertionError(f"unexpected axis: {axis}")
        return FakeVector([sum(row) for row in self.rows])

    def __eq__(self, other):
        return FakeArray(
            [
                [value == other for value in row]
                for row in self.rows
            ]
        )

    def __getitem__(self, item):
        if isinstance(item, tuple) and len(item) == 2:
            if isinstance(item[0], slice):
                _, column_slice = item
                return FakeArray([row[column_slice] for row in self.rows])
            batch_indices, sequence_lengths = item
            return FakeArray(
                [
                    self.rows[batch_index][token_index]
                    for batch_index, token_index in zip(batch_indices, sequence_lengths.values)
                ]
            )
        if isinstance(item, tuple) and len(item) == 3:
            row_selector, _, limit = item
            if not isinstance(row_selector, slice) or row_selector != slice(None):
                raise AssertionError("unexpected row selector")
            return FakeArray([row[:limit] for row in self.rows])
        return self.rows[item]

    def __truediv__(self, other):
        return FakeArray(
            [
                [value / divisor_row[0] for value in row]
                for row, divisor_row in zip(self.rows, other.rows)
            ]
        )


@dataclass
class FakeVector:
    values: list[float]

    def __sub__(self, other):
        return FakeVector([value - other for value in self.values])

    def __iter__(self):
        return iter(self.values)
