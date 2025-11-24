"""最小可執行的 MCP Server 範例（僅示範工具匯出）。"""
from toolanything import ToolRegistry, tool
from toolanything.adapters.mcp_adapter import export_tools

registry = ToolRegistry()


@tool(path="echo.text", description="回聲輸出", registry=registry)
def echo(text: str) -> dict:
    return {"echo": text}


def main():
    tools = export_tools(registry)
    print({"tools": tools})


if __name__ == "__main__":
    main()
