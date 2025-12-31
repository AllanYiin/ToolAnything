"""Quickstart: 定義一組最小工具集合。"""
from __future__ import annotations

from toolanything.decorators import tool
from toolanything.core.registry import ToolRegistry


@tool(
    name="quickstart.greet",
    description="打招呼，回傳客製化問候語",
    tags=["text", "demo"],
    metadata={
        "cost": 0.0,
        "latency_hint_ms": 50,
        "side_effect": False,
        "category": "demo",
        "tags": ["greeting", "intro"],
        "owner": "quickstart",
    },
)
def greet(name: str) -> str:
    return f"Hello {name}!"


@tool(
    name="quickstart.add",
    description="計算兩個整數的總和",
    tags=["math", "demo"],
    metadata={
        "cost": 0.01,
        "latency_hint_ms": 30,
        "side_effect": False,
        "category": "math",
        "tags": ["sum"],
        "owner": "quickstart",
    },
)
def add(a: int, b: int) -> int:
    return a + b


@tool(
    name="quickstart.store_note",
    description="寫入一行備忘（示意 side_effect=True）",
    tags=["note", "demo"],
    metadata={
        "cost": 0.05,
        "latency_hint_ms": 120,
        "side_effect": True,
        "category": "ops",
        "tags": ["write", "side_effect"],
        "owner": "quickstart",
    },
)
def store_note(message: str) -> dict:
    return {"status": "stored", "message": message}


if __name__ == "__main__":
    registry = ToolRegistry.global_instance()
    print("已註冊工具：")
    for spec in registry.list():
        print(f"- {spec.name} (side_effect={spec.normalized_metadata().side_effect})")
