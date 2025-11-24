from toolanything import ToolRegistry
from toolanything.adapters.openai_adapter import export_tools
from toolanything.decorators import tool


def test_docstring_metadata_attached_and_used_in_description():
    registry = ToolRegistry()

    @tool(path="demo.docs", description="基本描述", registry=registry)
    def annotated(a: int):
        """
        Usage: 當需要示範 docstring 擷取時使用
        Args:
            a: 要回傳的數值
        Returns:
            dict，包含 echo 結果
        """

        return {"value": a}

    definition = registry.get_tool("demo.docs")
    assert definition.documentation is not None
    hint = definition.documentation.to_prompt_hint()
    assert "使用時機" in hint

    tools = export_tools(registry)
    entry = next(t for t in tools if t["function"]["name"] == "demo.docs")
    description = entry["function"]["description"]

    assert "使用時機：當需要示範 docstring 擷取時使用" in description
    assert "參數說明：a: 要回傳的數值" in description
    assert "輸出格式：dict，包含 echo 結果" in description
