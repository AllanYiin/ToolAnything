"""Quickstart tools for MCP demo."""
from __future__ import annotations

from toolanything.decorators import tool


@tool(
    name="calculator.add",
    description="加總兩個整數",
    tags=["math", "demo"],
    metadata={
        "cost": 0.0,
        "latency_hint_ms": 5,
        "side_effect": False,
        "category": "demo",
    },
)
def add(a: int, b: int) -> int:
    return a + b


@tool(
    name="text.reverse",
    description="反轉字串",
    tags=["text", "demo"],
    metadata={
        "cost": 0.0,
        "latency_hint_ms": 3,
        "side_effect": False,
        "category": "demo",
    },
)
def reverse_text(text: str) -> str:
    return text[::-1]
