# Getting Started

這是一份以「第一次成功跑通一條完整路徑」為目標的入門文件。完成後，你會有一個可被 MCP host 發現與呼叫的工具，並知道如何用 CLI 與 inspector 驗證它。

## 你會完成什麼

1. 從 repo 安裝 ToolAnything
2. 用 `@tool` 定義一支工具
3. 啟動 MCP server
4. 驗證 `tools/list`、`tools/call` 與基礎診斷

## 前置條件

- Python `>=3.10`
- 可在本機執行 `pip`
- 已 clone 這個 repo

```bash
git clone https://github.com/AllanYiin/ToolAnything.git
cd ToolAnything
pip install -e .
```

如果你還要跑測試、ONNX 或 PyTorch 相關範例，請改裝開發依賴：

```bash
pip install -e .[dev]
```

## Step 1: 定義第一支工具

最小寫法如下：

```python
from toolanything import tool


@tool(name="calculator.add", description="加總兩個整數")
def add(a: int, b: int) -> int:
    return a + b
```

如果你想直接使用 repo 內建的最小範例，也可以直接沿用 `examples/quickstart/tools.py`。

## Step 2: 啟動 MCP server

本機最短路徑建議先用 `stdio`：

```bash
toolanything serve examples/quickstart/tools.py --stdio
```

如果你要做 HTTP 型整合，再改用 Streamable HTTP：

```bash
toolanything serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
```

說明：

- `--stdio` 適合 Claude Desktop 這類會用 subprocess 啟動工具的 host
- `--streamable-http` 會在 `/mcp` 提供新版 MCP HTTP transport
- 如果你不加任何 transport flag，`serve` 預設會啟動 legacy HTTP/SSE server

## Steps

把這份入門想成固定四步：

1. 安裝 ToolAnything
2. 定義一支最小工具
3. 啟動 transport
4. 驗證 `tools/list` 與 `tools/call`

## Step 3: 驗證 server 真的可用

### 驗證 stdio

```bash
toolanything doctor --mode stdio --tools examples.quickstart.tools
```

### 驗證 HTTP

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
```

如果你想自己開一個互動式檢查畫面：

```bash
toolanything inspect
```

`inspect` 適合做這些事情：

- 看工具 schema
- 手動送 `tools/call`
- 檢查 MCP transcript
- 做 OpenAI tool-calling smoke test

## Step 4: 驗證成功條件

### Expected result

你應該能得到一個可被 MCP host 發現的工具服務，而不是只有一段已註冊的 Python 程式碼。

至少確認下列幾件事：

- `tools/list` 能看到你剛註冊的工具
- `tools/call` 能成功回傳結果
- `doctor` 報告沒有初始化或 transport 失敗
- 若使用 HTTP 模式，server 可以穩定回應 `/mcp` 或 legacy 端點

## 常見失敗

### 找不到 `toolanything`

原因通常是尚未安裝套件，或 shell 沒拿到目前虛擬環境。先重新執行：

```bash
pip install -e .
```

### 找不到工具模組檔案

`serve` 同時支援模組路徑與 `.py` 檔案路徑。如果你不在 repo root，請改用絕對路徑或切回 repo root 再執行。

### `doctor` 成功但 host 連不上

先確認你選對 transport。Desktop 類 host 通常需要 `--stdio`；網路型整合才是 Streamable HTTP 或 legacy HTTP/SSE。

## 下一步

- 想了解不同工具來源：看 [Tool Definition and Registration](Tool-Definition-and-Registration)
- 想選 transport：看 [MCP Serving and Transports](MCP-Serving-and-Transports)
- 想看完整學習路線：看 [Examples and Learning Paths](Examples-and-Learning-Paths)
