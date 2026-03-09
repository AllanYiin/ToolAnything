# Migration Guide

本文件說明 ToolAnything 從 callable-first 遷移到 invoker-first / source-based API 的方式。

## 先講結論

- 舊的 `@tool`、`ToolSpec.from_function()`、`ToolManager.register(function)` 仍然可用。
- 新核心不再把 Python callable 視為唯一工具來源。
- 建議新功能優先使用 source-based API：
  - HTTP API：`register_http_tool(...)`
  - SQL query：`register_sql_tool(...)`
  - PyTorch / ONNX inference：`register_model_tool(...)`

## 舊用法：callable-first

```python
from toolanything import tool

@tool(name="math.add", description="兩數相加")
def add(a: int, b: int = 1) -> int:
    return a + b
```

這個用法仍然有效，內部會自動包成 `CallableInvoker`，並透過 invoker runtime 執行。

## 新用法：invoker-first / source-based

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
        query_params=(HttpFieldSpec("include", {"type": "string"}),),
        auth_ref="env:API_TOKEN",
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
        input_spec={
            "input": {"kind": "tensor", "dtype": "float32", "shape": [2]}
        },
    )
)
```

## 何時用哪種 source

- `callable`：你本來就有 Python 函式，且它是核心業務邏輯本體。
- `http`：你要包裝外部 REST API，而且不想再手寫 wrapper function。
- `sql`：你要暴露固定模板查詢，並希望 schema 自動從 bind params 推導。
- `model`：你要把 inference runtime 納入正式工具來源，而不是塞進一般函式裡。

## 相容層說明

目前仍保留以下 compatibility layer：

- `@tool`
- `ToolSpec.from_function()`
- `ToolRegistry.get() -> callable`，僅適用 callable-backed tools
- `ToolRegistry.execute_tool_async()`，內部會委派到新的 `invoke_tool_async()`

這些 API 不是這輪要刪除的對象，但新擴充功能不應再依賴它們作為核心抽象。

## 新分層

- `SourceSpec`：來源設定，例如 HTTP/SQL/model。
- `ToolContract`：name / description / schema / metadata。
- `Invoker`：真正的執行體。
- `Runtime`：建立 `ExecutionContext`、呼叫 invoker、維持 compatibility。
- `Transport`：MCP stdio / legacy SSE / Streamable HTTP，只處理 I/O。

## 本輪明確不做

- skill as tool
- 完整 OpenAPI importer
- GraphQL source
- model training orchestration

`skill as tool` 已明確留到下一輪，不在本次 migration scope。
