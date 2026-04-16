# Standard tools examples

這個資料夾示範如何把 ToolAnything 內建標準工具集註冊到同一個
`ToolRegistry`，並同時輸出 OpenAI、MCP 與 CLI metadata。

標準工具集本體位於 `src/toolanything/standard_tools/`。這是正式套件
功能，應該跟其他可匯入 API 一樣留在 `src`。`examples/standard_tools/`
只放使用範例，避免範例程式被誤當成 runtime 來源。

## 執行順序

請在 repo root 執行：

```bash
python examples/standard_tools/01_register_and_export.py
python examples/standard_tools/02_write_tools_opt_in.py
python examples/standard_tools/03_provider_search.py
```

## 範例內容

| 檔案 | 目的 |
| --- | --- |
| `01_register_and_export.py` | 註冊預設唯讀工具，呼叫 `standard.fs.read_text` 與 `standard.data.json_parse`，並展示 `to_openai()`、`to_mcp()`、`to_cli()` 的輸出形狀 |
| `02_write_tools_opt_in.py` | 示範寫入工具必須同時啟用 `include_write_tools=True` 與 writable root，並用 SHA-256 guard 更新檔案 |
| `03_provider_search.py` | 示範 `standard.web.search` 如何接入 host 自己提供的搜尋 provider |

## 重要邊界

- MCP metadata 使用 `inputSchema`。
- OpenAI function tool metadata 使用 `function.parameters` 與 `function.strict`。
- CLI metadata 使用 `commandPath` 與 arguments。
- `standard.web.fetch` 是文字型 HTTP fetch，不負責 PDF 解析。
- 寫入工具預設不註冊；需要 host 明確設定 writable root。

