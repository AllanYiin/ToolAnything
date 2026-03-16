# Workflow

## 決策矩陣

| 情況 | 優先做法 | 不要做什麼 | 依據 |
| --- | --- | --- | --- |
| 已有純 Python function | 用 `@tool` 直接註冊 | 再包一層多餘 adapter | `examples/quickstart/01_define_tools.py` |
| 已有 class method | 用 `@tool` 加 `@classmethod` 任一支援順序 | 自己重寫 descriptor 邏輯 | `examples/class_method_tools/README.md` |
| 實際來源是 HTTP API | 用 `HttpSourceSpec` + `register_http_tool` | 人工再寫一支只會轉呼叫的薄 wrapper | `examples/non_function_tools/http_tool.py` |
| 實際來源是 SQL query | 用 `SqlSourceSpec` + `register_sql_tool` | 把 SQL 塞進普通函數後假裝是 function tool | `examples/non_function_tools/sql_tool.py` |
| 實際來源是 model artifact | 用 `ModelSourceSpec` + `register_model_tool` | 先多包一層無意義 service | `README.md` 與 `examples/non_function_tools/` |

## 最短路徑

### A. 新增一般函數 tool

1. 在最接近業務邏輯的模組新增函數。
2. 補上型別標註。
3. 加上 `@tool(name=..., description=...)`。
4. 只有在搜尋、治理或成本預估真的重要時才補 `tags` / `metadata`。
5. 用 registry 或 CLI 驗證。

範例骨架：

```python
from toolanything import tool


@tool(name="calculator.add", description="加總兩個整數")
def add(a: int, b: int) -> int:
    return a + b
```

### B. 新增 class method tool

兩種 decorator 順序都支援，但要維持同一模組風格一致：

```python
class Greeter:
    @tool(name="greeting.class_hello", description="由 class method 產生問候語")
    @classmethod
    def hello(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"
```

### C. 換成 source-based tool

當需求其實是「把外部能力宣告成工具」時，用 source-based API 比 function wrapper 更誠實：

```python
from toolanything import HttpFieldSpec, HttpSourceSpec, ToolManager

manager = ToolManager()
manager.register_http_tool(
    HttpSourceSpec(
        name="users.fetch",
        description="取得使用者資料",
        method="GET",
        base_url="https://example.com",
        path="/users/{user_id}",
        path_params=(HttpFieldSpec("user_id", {"type": "string"}, required=True),),
    )
)
```

## 命名規則

1. 名稱優先用穩定的領域與動作，像 `domain.action`。
2. 避免把暫時實作細節寫進 tool name。
3. description 直接描述工具做什麼，不要寫成開發者備忘錄。
4. 如果工具可能有副作用，metadata 要明確標示，不要讓 agent 猜。

## 何時要直接糾正使用者

遇到以下情況要直接說明，而不是照做：

1. 使用者要求手寫第二套 MCP / OpenAI schema，但 repo 已有對應輸出。
2. 使用者想把 HTTP / SQL / model 問題硬說成「只是包個 function」。
3. 使用者要求為了單一案例改壞既有工具名稱或公開契約。
