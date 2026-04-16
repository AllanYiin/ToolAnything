# Standard Tools

標準工具集是 ToolAnything 提供的一組可重用工具能力，目標是讓 agent host
不用每個專案都重新包一套 web、filesystem、data helper。它不是 demo code，
而是正式套件功能。

## 放在 `src` 還是 `examples`

標準工具集本體應放在 `src/toolanything/standard_tools/`。

理由：

- 它是可被外部專案 `import toolanything` 使用的公開能力。
- 它需要跟 `ToolRegistry`、MCP export、OpenAI export、CLI export 共用同一份
  contract。
- 它有安全策略、resource limits、metadata schema 與測試，這些都屬於 runtime
  與平台能力，不是一次性示範。
- 放在 `examples/` 會讓使用者誤以為它只是參考程式，也會讓 package 發布、
  type import 與測試邊界變得不清楚。

`examples/standard_tools/` 應只放「如何使用」的範例。

## 快速開始

```python
from pathlib import Path

from toolanything import (
    StandardToolOptions,
    ToolRegistry,
    register_standard_tools,
)

registry = ToolRegistry()
register_standard_tools(
    registry,
    StandardToolOptions(roots={"workspace": Path.cwd()}),
)
```

預設註冊的是安全優先的唯讀集合：

- `standard.web.*`：文字型 HTTP fetch、HTML text/link extraction、provider-backed search。
- `standard.fs.*`：root-scoped list、stat、read_text、search。
- `standard.data.*`：JSON、JSON Schema subset、CSV、Markdown、JSONL、TOML、YAML、XML inspection。

不會預設註冊：

- filesystem 寫入工具。
- browser provider 工具。
- shell、process、code execution、cron、memory、delegation 這類高風險能力。

## Metadata Export

同一個 `ToolSpec` 可以輸出三種正式 metadata。

```python
spec = registry.get_tool("standard.fs.read_text")

openai_tool = spec.to_openai()
mcp_tool = spec.to_mcp()
cli_tool = spec.to_cli()
```

MCP 使用 `inputSchema`：

```json
{
  "name": "standard.fs.read_text",
  "description": "...",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

OpenAI function tool 使用 `function.parameters` 與 `function.strict`：

```json
{
  "type": "function",
  "function": {
    "name": "standard_fs_read_text",
    "parameters": {
      "type": "object",
      "additionalProperties": false
    },
    "strict": true
  }
}
```

CLI export 使用 `commandPath`：

```json
{
  "commandPath": ["standard", "fs", "read-text"],
  "arguments": {}
}
```

完整 host manifest 可用：

```python
manifest = registry.to_tool_manifest(tags=["standard"])
schema = registry.tool_manifest_schema()
```

manifest 會包含 `metadata`、`openai`、`mcp`、`cli`，適合 host UI、policy engine
或 agent runtime 使用。

## 執行範例

請在 repo root 執行：

```bash
python examples/standard_tools/01_register_and_export.py
python examples/standard_tools/02_write_tools_opt_in.py
python examples/standard_tools/03_provider_search.py
```

範例用途：

| 檔案 | 學到什麼 |
| --- | --- |
| `01_register_and_export.py` | 註冊預設工具、呼叫讀檔與 JSON parse、檢查 OpenAI/MCP/CLI metadata |
| `02_write_tools_opt_in.py` | 啟用 guarded write tools，並用 SHA-256 guard 更新檔案 |
| `03_provider_search.py` | 替 `standard.web.search` 接 host 自己的搜尋 provider |

## Filesystem Root Model

filesystem 工具都透過 named root 執行。呼叫工具時傳入 `root_id` 與
`relative_path`，而不是讓模型直接碰任意絕對路徑。

```python
register_standard_tools(
    registry,
    StandardToolOptions(roots={"workspace": Path.cwd()}),
)
```

寫入工具需要兩層 opt-in：

```python
from toolanything import StandardToolRoot

register_standard_tools(
    registry,
    StandardToolOptions(
        roots=(StandardToolRoot("workspace", Path.cwd(), writable=True),),
        include_write_tools=True,
    ),
)
```

寫入工具的保護：

- `standard.fs.write_create_only`：目標存在就失敗。
- `standard.fs.replace_if_match`：需要目前檔案 SHA-256。
- `standard.fs.patch_text`：預設只預覽；實際套用需要 SHA-256。
- `standard.fs.apply_unified_patch`：一次只處理單檔 patch，並驗證 hunk context。

## Web Fetch 與 PDF

`standard.web.fetch` 應維持為文字型 HTTP fetch，不應直接讀取 web PDF。

原因：

- PDF 不是文字資源；解析需要額外 parser、頁數限制、物件限制與 sandbox policy。
- PDF 常包含大型 binary stream、嵌入檔、圖片與複雜字型，風險與 HTML/text fetch 不同。
- 將 PDF 塞進 `web_fetch` 會讓 metadata 描述失真，host 也難以對 PDF 解析成本做獨立控管。

建議做法是另外提供 opt-in document tool，例如 `standard.document.pdf_extract_text`，
並定義清楚的 byte limit、page limit、timeout、parser dependency、錯誤格式與 output schema。

目前 `standard.web.fetch`：

- 只接受 HTTP(S)。
- 擋掉 private、loopback、link-local、reserved、multicast、metadata host 等 SSRF 高風險目標。
- 驗證 redirect 與連線後 peer IP。
- 對 response size 設定 `max_web_bytes`。
- 阻擋 `application/pdf`，也會拒絕 body 以 `%PDF-` 開頭的回應。

## Provider-backed Search

`standard.web.search` 需要 host 提供 provider。

```python
from toolanything import StandardSearchResult

def search_provider(query: str, limit: int):
    return [
        StandardSearchResult(
            title="Result",
            url="https://example.com",
            snippet=query,
            source="demo",
        )
    ][:limit]

register_standard_tools(
    registry,
    StandardToolOptions(search_provider=search_provider),
)
```

provider 需自行負責：

- API key 與 quota。
- timeout 與重試。
- privacy policy。
- 不把 secrets 或內部 URL 回傳給模型，除非 host 已明確建立該信任邊界。

## Resource Limits

標準工具集預設採保守限制：

- data tools 會檢查 `max_read_chars`。
- XML inspection 拒絕 DTD 與 ENTITY。
- filesystem search 有 ignored dirs、file size、file count 與 timeout policy。
- web fetch 有 timeout、redirect count、content type 與 byte limit。

這些限制不是 UX 裝飾，而是 agent host 的穩定性邊界。若 host 需要放寬，應該由
`StandardToolOptions` 明確設定，並在產品層同步顯示風險。

## Runtime Policy

可用 metadata policy 在呼叫前攔截工具：

```python
from toolanything import MetadataToolPolicy, ToolRegistry

registry = ToolRegistry(
    execution_policy=MetadataToolPolicy(
        allowed_scopes={"fs:read", "data:transform", "net:http:get", "net:search"},
        block_side_effects=True,
    )
)
```

policy 會檢查 `metadata["scopes"]`、`metadata["side_effect"]` 與
`metadata["requires_approval"]`。MCP annotations 只是 host hint，不應取代 runtime policy。

## 驗證

標準工具集相關測試：

```bash
pytest tests/test_standard_tools.py
```

新增或修改 metadata export 時，也應檢查：

```bash
python examples/standard_tools/01_register_and_export.py
```

輸出裡應能看到：

- MCP metadata 有 `inputSchema`。
- OpenAI metadata 有 `function.parameters` 與 `strict: true`。
- CLI metadata 有 `commandPath`。

