"""Weather tool 範例：以 ToolAnything 定義 OpenAI/MCP 共享工具。"""
from toolanything import ToolRegistry, tool

registry = ToolRegistry()


@tool(path="weather.query", description="取得城市目前溫度", registry=registry)
def query_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}


def main():
    # 直接呼叫 Python 函數
    print(query_weather("Taipei"))

    # OpenAI tool schema 輸出
    print(registry.to_openai_tools())


if __name__ == "__main__":
    main()
