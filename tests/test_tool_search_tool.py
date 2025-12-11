import pytest

from toolanything.core import FailureLogManager, ToolRegistry, ToolSearchTool
from toolanything.core.models import ToolSpec


def _translate_text() -> str:
    """翻譯文字內容。"""

    return ""


def _translate_audio() -> str:
    """翻譯音訊內容。"""

    return ""


def _helper_tool() -> str:
    """一般輔助工具。"""

    return ""


def test_failure_log_manager_records_and_calculates(tmp_path):
    log_path = tmp_path / ".tool_failures.json"
    manager = FailureLogManager(log_path)

    manager.record_failure("demo", timestamp=100.0)
    manager.record_failure("demo", timestamp=101.0)

    record = manager.get_record("demo")
    assert record is not None
    assert record["count"] == 2
    assert log_path.exists()

    latest_score = manager.failure_score("demo", now=101.0)
    assert latest_score == pytest.approx(2.0)

    decayed = manager.failure_score("demo", now=106.0)
    assert decayed < latest_score


def test_tool_search_filters_and_sorts_by_failure():
    registry = ToolRegistry()
    registry.register(
        ToolSpec.from_function(
            _translate_text,
            name="translate.text",
            description="翻譯文字內容",
            tags=["lang", "text"],
        )
    )
    registry.register(
        ToolSpec.from_function(
            _translate_audio,
            name="translate.audio",
            description="翻譯音訊內容",
            tags=["lang", "audio"],
        )
    )
    registry.register(
        ToolSpec.from_function(
            _helper_tool,
            name="helper.tool",
            description="一般輔助任務",
            tags=["misc"],
        )
    )

    failure_log = FailureLogManager()
    failure_log.record_failure("translate.text", timestamp=500.0)

    searcher = ToolSearchTool(registry, failure_log)
    results = searcher.search(query="translate", tags=["lang"], top_k=2, now=500.0)
    assert [spec.name for spec in results] == ["translate.audio", "translate.text"]

    prefixed = searcher.search(prefix="translate.", now=500.0)
    assert all(spec.name.startswith("translate.") for spec in prefixed)
    assert any(spec.name == "translate.text" for spec in prefixed)
    assert any(spec.name == "translate.audio" for spec in prefixed)
