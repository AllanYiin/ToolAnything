# Tool Definition and Registration

這一頁回答的是：「ToolAnything 裡的 tool 到底怎麼來？」如果你只記一件事，就是 ToolAnything 已不再把 Python callable 視為唯一工具來源。現在有兩條正式路線：callable-first 與 source-based。

## 路線 1：用 `@tool` 包 Python function

這是最短上手路徑：

```python
from toolanything import tool


@tool(name="weather.query", description="取得城市天氣")
def get_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}
```

適合情境：

- 你的核心邏輯本來就是 Python function
- 你想先快速得到 MCP 與 OpenAI schema
- 你想先把工具註冊、搜尋與呼叫流程跑通

## 路線 1b：直接包 class method

ToolAnything 現在支援 class method，而且 `@tool` 與 `@classmethod` 兩種順序都能工作。

```python
class Greeter:
    @tool(name="classmethod.outer_order", description="示範 @tool 在外")
    @classmethod
    def greet(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"
```

何時用：

- 你的工具邏輯需要綁在類別結構上
- 你想保留一般 class method 的呼叫方式
- 你不想手動包一層 module-level wrapper

如果你要看兩種 decorator 順序的完整說明，請直接跑 `examples/class_method_tools/README.md`。

## 路線 2：用 source-based API 直接註冊外部來源

如果工具的本體其實是 API、SQL 或模型推論，建議改走 source-based API，而不是先手寫一層低價值 wrapper。

### HTTP tool

```python
from toolanything import HttpFieldSpec, HttpSourceSpec, ToolManager

manager = ToolManager()
manager.register_http_tool(
    HttpSourceSpec(
        name="users.fetch",
        description="取得使用者",
        method="GET",
        base_url="https://api.example.com",
        path="/users/{user_id}",
        path_params=(HttpFieldSpec("user_id", {"type": "string"}, required=True),),
    )
)
```

### SQL tool

```python
from toolanything import InMemorySQLConnectionProvider, SqlSourceSpec, ToolManager

provider = InMemorySQLConnectionProvider()
provider.register_sqlite("warehouse.main", database="analytics.db")

manager = ToolManager()
manager.register_sql_tool(
    SqlSourceSpec(
        name="analytics.top_scores",
        description="查詢分數",
        connection_ref="warehouse.main",
        query_template="SELECT id, score FROM users WHERE team = :team",
        param_schemas={"team": {"type": "string"}},
    ),
    connection_provider=provider,
)
```

### Model tool

```python
from toolanything import ModelSourceSpec, ToolManager

manager = ToolManager()
manager.register_model_tool(
    ModelSourceSpec(
        name="models.double",
        description="執行張量推論",
        model_type="pytorch",
        artifact_path="double.pt",
        input_spec={"input": {"kind": "tensor", "dtype": "float32", "shape": [2]}},
    )
)
```

## 什麼時候該選哪條路

| 來源 | 建議用法 |
| --- | --- |
| 既有 Python function / class method | `@tool` 或 `ToolManager.register(...)` |
| 外部 REST API | `register_http_tool(...)` |
| 固定模板 SQL 查詢 | `register_sql_tool(...)` |
| ONNX / PyTorch 推論 | `register_model_tool(...)` |

## metadata 與工具搜尋

工具數量變多後，搜尋與排序會開始依賴 metadata。`toolanything search` 目前會輸出這些常見欄位：

- `cost`
- `latency_hint_ms`
- `side_effect`
- `category`
- `tags`

這些欄位會被搜尋策略拿來做條件篩選與排序，所以如果你的工具會被大量混用，建議一開始就定義好 metadata。

## 驗證註冊是否成功

最簡單的檢查方式有三種：

1. `toolanything search --query <keyword>`
2. `toolanything doctor`
3. 用 `toolanything inspect` 看 `tools/list`

## 相關文件

- [Getting Started](Getting-Started)
- [MCP Serving and Transports](MCP-Serving-and-Transports)
- [Migration Guide](Migration-Guide)
