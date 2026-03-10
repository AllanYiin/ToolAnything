"""Packaged Tool Selection example catalog."""
from __future__ import annotations

from toolanything.core.registry import ToolRegistry
from toolanything.decorators import tool


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @tool(
        name="catalog.summarize",
        description="摘要一段文字",
        registry=registry,
        tags=["text", "summary"],
        metadata={
            "cost": 0.02,
            "latency_hint_ms": 800,
            "side_effect": False,
            "category": "nlp",
            "tags": ["summarize"],
            "owner": "catalog",
        },
    )
    def summarize(text: str) -> str:
        return text[:60] + ("..." if len(text) > 60 else "")

    @tool(
        name="catalog.translate_quality",
        description="高品質文件翻譯",
        registry=registry,
        tags=["text", "translate", "document"],
        metadata={
            "cost": 0.06,
            "latency_hint_ms": 1800,
            "side_effect": False,
            "category": "nlp",
            "tags": ["translation", "quality"],
            "owner": "catalog",
        },
    )
    def translate_quality(text: str, target_lang: str = "en") -> str:
        return f"[quality:{target_lang}] {text}"

    @tool(
        name="catalog.translate_fast",
        description="快速短句翻譯",
        registry=registry,
        tags=["text", "translate", "realtime"],
        metadata={
            "cost": 0.015,
            "latency_hint_ms": 150,
            "side_effect": False,
            "category": "nlp",
            "tags": ["translation", "fast"],
            "owner": "catalog",
        },
    )
    def translate_fast(text: str, target_lang: str = "en") -> str:
        return f"[{target_lang}] {text}"

    @tool(
        name="catalog.send_email",
        description="寄送 email（示意 side_effect=True）",
        registry=registry,
        tags=["notify", "email"],
        metadata={
            "cost": 0.1,
            "latency_hint_ms": 300,
            "side_effect": True,
            "category": "ops",
            "tags": ["email", "notify"],
            "owner": "catalog",
        },
    )
    def send_email(to: str, subject: str, body: str) -> dict:
        return {"status": "queued", "to": to, "subject": subject}

    @tool(
        name="catalog.calculate_tax",
        description="試算稅額",
        registry=registry,
        tags=["finance", "calc"],
        metadata={
            "cost": 0.01,
            "latency_hint_ms": 60,
            "side_effect": False,
            "category": "finance",
            "tags": ["tax"],
            "owner": "catalog",
        },
    )
    def calculate_tax(amount: float, rate: float = 0.05) -> float:
        return amount * rate

    return registry


def describe_registry(registry: ToolRegistry) -> list[str]:
    lines: list[str] = []
    for spec in registry.list():
        metadata = spec.normalized_metadata()
        lines.append(
            f"- {spec.name} (cost={metadata.cost}, latency={metadata.latency_hint_ms}, "
            f"side_effect={metadata.side_effect}, category={metadata.category})"
        )
    return lines
