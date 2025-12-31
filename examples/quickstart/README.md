# Quickstart（最小可跑）

這份範例會示範：
- 註冊工具（`examples/quickstart/tools.py`）
- 以 **stdio** 模式啟動 MCP server
- 依序完成 `initialize`、`tools/list`、`tools/call`
- 使用工具搜尋（ToolSearchTool）

> 下列指令都在 repo 根目錄執行。

## 1) 安裝依賴

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2) 註冊工具（已在 tools.py 定義）

工具範例定義在 `examples/quickstart/tools.py`：

- `calculator.add`：加總兩個整數
- `text.reverse`：反轉字串

## 3) 啟動 MCP stdio server + 完整 MCP 流程

以下指令會**自動啟動** stdio server，並依序送出：
`initialize` → `notifications/initialized` → `tools/list` → `tools/call`。

```bash
python examples/quickstart/stdio_roundtrip.py
```

你會看到類似輸出（省略部分內容）：

```text
initialize: {"jsonrpc": "2.0", "id": 1, "result": { ... }}
tools/list: {"jsonrpc": "2.0", "id": 2, "result": {"tools": [ ... ]}}
tools/call: {"jsonrpc": "2.0", "id": 3, "result": { ... }}
```

## 4) 工具搜尋（ToolSearchTool）

```bash
python examples/quickstart/search_tools.py --query "加總"
```

這個步驟會透過 `ToolSearchTool.search()` 搜尋已註冊工具，並回傳 metadata。

---

## 檔案位置一覽

- 工具定義：`examples/quickstart/tools.py`
- MCP roundtrip：`examples/quickstart/stdio_roundtrip.py`
- 工具搜尋：`examples/quickstart/search_tools.py`
