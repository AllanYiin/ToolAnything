# CLI Export

ToolAnything 現在除了 MCP 與 OpenAI tool calling，也能把同一份 `ToolContract` 投影成 CLI command tree，而且實際執行仍走既有 `ToolRegistry.invoke_tool_async()` 與 invoker/runtime 路徑。

## 這個功能解決什麼

- 不需要再手寫另一套 argparse wrapper
- CLI / MCP / OpenAI 共用同一份 schema，降低參數漂移
- 可以直接用在 shell、CI、smoke test 與人工驗證

## 快速開始

假設你的工具模組是 `tests.fixtures.sample_tools`：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools
toolanything cli run --config toolanything.cli.json -- math add --a 2 --b 3 --json
```

如果你想產生可直接執行的 launcher：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools --launcher .toolanything/mytools.py
python .toolanything/mytools.py math add --a 2 --b 3
```

## 管理指令

- `toolanything cli export`: 生成並保存 CLI project config
- `toolanything cli run`: 依 module 或 config 動態執行 CLI app
- `toolanything cli inspect`: 輸出 command tree / arguments JSON
- `toolanything cli show-config`: 顯示保存的 project config
- `toolanything cli delete-project`: 刪除 project config，可選擇一併刪除 launcher

預設 config 檔名是 `toolanything.cli.json`。

## 命名規則

- `weather.query` -> `weather query`
- 單段工具名直接成為單一命令
- 非英數字元會正規化成 `-`
- 命名或 alias 衝突會中止生成並回傳專屬錯誤
- 若要直接在 `@tool(...)` 指定 CLI 指令，可加 `cli_command="wx current"`

```python
from toolanything import tool


@tool(
    name="weather.query",
    description="查詢目前天氣",
    cli_command="wx current",
)
def weather(city: str) -> dict:
    return {"city": city}
```

`toolanything.cli.json` 內的 `command_overrides` 仍有最高優先權，適合在不改原始 tool 定義時做最後覆寫。

## 參數映射

- `string` -> `--name value`
- `integer` / `number` -> `--count 3`
- `boolean` 預設 `false` -> `--flag`
- `boolean` 預設 `true` -> `--no-flag`
- `array` -> 重複 option
- `object` -> `--body '{"a":1}'` 或 `--body @payload.json`

檔案路徑欄位會先檢查存在性，成功執行後會附上 artifact 摘要。

## 輸出與 exit code

- `--json`: 輸出穩定 envelope
- `--output <path>`: 輸出到檔案
- `--overwrite`: 允許覆寫既有輸出檔
- `--verbose` / `--quiet`: 控制輸出冗長度
- `--stream`: 要求串流輸出；目前 CLI 端預留路徑，底層工具若未實作 stream emitter，會退回聚合輸出

主要 exit code：

- `0`: success
- `2`: argument validation error
- `3`: command resolution error
- `4`: runtime invocation error
- `5`: tool execution error
- `6`: output serialization error
- `7`: project config error
- `8`: naming conflict error
- `9`: unsupported feature
- `130`: interrupted

## Project Config

`toolanything.cli.json` 會保存：

- app 名稱與描述
- 預設輸出模式
- tool 清單
- command overrides
- module 路徑
- launcher 路徑

你可以重新載入 config 後再 `export` 或 `run`，不需要重建整個 CLI 定義。

## 目前邊界

- 第一版沒有新增 CLI source 類型
- 第一版沒有做 REPL
- 複雜巢狀 object 主要透過 JSON string / `@file.json` 傳入
- aspect ratio 驗證目前採 metadata 驅動：`metadata["cli"]["aspect_ratio"]`
- stream emitter 路徑已打通到 registry，但要有真正逐 token 輸出，工具端仍需實作
