"""Class method tutorial demo for ToolAnything."""
from __future__ import annotations

import asyncio

from toolanything import ToolRegistry, tool

registry = ToolRegistry()


class OuterToolOrder:
    @tool(name="classmethod.outer_order", description="示範 @tool 在外、@classmethod 在內", registry=registry)
    @classmethod
    def greet(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"


class OuterClassMethodOrder:
    @classmethod
    @tool(name="classmethod.inner_order", description="示範 @classmethod 在外、@tool 在內", registry=registry)
    def greet(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"


async def main() -> None:
    print("已註冊工具：")
    for spec in registry.list():
        print(f"- {spec.name}: {spec.description}")

    print("\n直接呼叫 class method：")
    print(OuterToolOrder.greet("Ada"))
    print(OuterClassMethodOrder.greet("Grace"))

    print("\n透過 registry.invoke_tool_async 呼叫：")
    print(await registry.invoke_tool_async("classmethod.outer_order", arguments={"name": "Ada"}))
    print(await registry.invoke_tool_async("classmethod.inner_order", arguments={"name": "Grace"}))


if __name__ == "__main__":
    asyncio.run(main())
