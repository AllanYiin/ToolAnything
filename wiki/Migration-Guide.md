# Migration Guide

這份文件說明 ToolAnything 從 callable-first 遷移到 invoker-first / source-based API 的方式，以及哪些舊用法仍然有效。

## Summary

- 舊的 `@tool`、`ToolSpec.from_function()`、`ToolManager.register(function)` 仍然可用
- callable 相容層現在也涵蓋 class method
- 新核心不再把 Python callable 視為唯一工具來源
- 新功能建議優先採用 source-based API

## 舊用法：callable-first

```python
from toolanything import tool

@tool(name="math.add", description="兩數相加")
def add(a: int, b: int = 1) -> int:
    return a + b
```

這條路線仍然有效。內部會自動包成 `CallableInvoker`，並透過新的 runtime 執行。

## 新用法：source-based

建議對照你的來源型別選 API：

- HTTP API：`register_http_tool(...)`
- SQL query：`register_sql_tool(...)`
- PyTorch / ONNX inference：`register_model_tool(...)`

## 何時用哪種來源

| 情境 | 建議來源 |
| --- | --- |
| 既有 Python 業務函式或 class method | `callable` |
| 要包外部 REST API | `http` |
| 要暴露固定模板查詢 | `sql` |
| 要把 inference runtime 變正式工具 | `model` |

## Breaking Changes

嚴格來說，這一輪的重點不是大規模砍掉舊 API，而是把核心抽象改成 invoker-first。真正需要你調整心智模型的 breaking change 在這裡：

- 不應再把 callable 視為唯一工具來源
- 新增功能時，不應把 transport、schema 與 callable 執行邏輯綁在一起
- 若你要新增 HTTP / SQL / model 工具，最佳入口已改成 source-based API

## 相容層仍保留哪些能力

目前保留：

- `@tool`
- `ToolSpec.from_function()`
- `ToolRegistry.get() -> callable`，僅限 callable-backed tools
- `ToolRegistry.execute_tool_async()`，內部會委派到新的 `invoke_tool_async()`

意思是：

- 你現有程式通常不需要立刻重寫
- 但新擴充點不該再把 callable-first 當核心抽象
- compatibility layer 是過渡層，不是未來擴充的主戰場

## 新分層心智模型

- `SourceSpec`：來源設定
- `ToolContract`：工具契約
- `Invoker`：執行邏輯
- `Runtime`：上下文與呼叫
- `Transport`：stdio / Streamable HTTP / legacy HTTP/SSE

如果你現在還把 transport、callable 與 schema 綁成同一層，遷移後最重要的改變是把這些責任切開。

## Upgrade Steps

1. 盤點你目前的工具來源，是 callable、HTTP、SQL 還是 model
2. 確認哪些舊程式只需要相容層，哪些新功能值得改成 source-based
3. 若有 class method 工具，確認目前是沿用新支援能力，而不是自製 wrapper

## 驗證方式

至少跑一次：

- `toolanything doctor`
- `toolanything inspect`
- 你的目標 host 整合 smoke test

如果你同時支援 OpenAI tool calling，也建議補跑 `OpenAIChatRuntime` 的最小 roundtrip。

換句話說，升級完成後一定要 verify transport、tool registry 與實際 host 整合是否都還正常。

## Rollback

如果升級後你需要回退，原則上先退回「舊 callable API 照常使用，但暫不導入 source-based 重構」的狀態。換句話說，先撤掉新 source-based 接法，而不是連既有 `@tool` 路線一起拆掉。

## Known issues

本輪文件已明確列出幾個不在範圍內的方向：

- skill as tool
- 完整 OpenAPI importer
- GraphQL source
- model training orchestration

## 相關文件

- [Tool Definition and Registration](Tool-Definition-and-Registration)
- [Architecture Walkthrough](Architecture-Walkthrough)
- [Diagnostics and Troubleshooting](Diagnostics-and-Troubleshooting)
