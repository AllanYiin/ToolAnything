# OpenCV MCP Web 教程

這個範例只存在於 repo 的 [`examples/opencv_mcp_web/`](/D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web)。

- `toolanything` 本體不再內建 package 內 demo module。
- 要跑範例時，直接用 repo 內檔案路徑。
- 這樣做的目的，是讓範例結構和你自己的專案一致，而不是把教學寫死在 package 內。

這個範例會帶你跑通一條完整鏈路：

1. 用 ToolAnything 把 OpenCV 函式包成 MCP 工具
2. 啟動本機 MCP Server
3. 用內建 MCP client 驗證 `initialize` / `tools/list` / `tools/call`
4. 用專用 Web UI 實際呼叫 `opencv.info`、`opencv.resize`、`opencv.canny`、`opencv.clahe`、`opencv.adjust_color`

這份教學預設走 **Streamable HTTP**（`/mcp`）路線，Web UI 也會直接對 `/mcp` 發送 `tools/list` / `tools/call`。

## 前置條件

以下命令以「你已安裝 `toolanything` 套件，且工作目錄在 repo 根目錄」為前提。

如果你的環境還沒有 `toolanything` CLI，也可以把命令中的 `toolanything` 改成：

```powershell
python -m toolanything.cli ...
```

如果你的 Web UI 會跑在 `http://127.0.0.1:5173`，建議先把允許來源設好：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```

## 步驟 1：啟動 MCP Server

```powershell
toolanything serve examples/opencv_mcp_web/server.py --streamable-http --host 127.0.0.1 --port 9091
```

成功後本機會有一個 MCP HTTP server 跑在：

```text
http://127.0.0.1:9091
```

Streamable HTTP 的 MCP 端點是：

```text
http://127.0.0.1:9091/mcp
```

## 步驟 2：確認 server 真的有起來

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9091/health | Select-Object -ExpandProperty Content
```

預期結果：

```json
{"status":"ok"}
```

再檢查工具列表：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9091/tools | Select-Object -ExpandProperty Content
```

預期至少要看到：

- `opencv.info`
- `opencv.resize`
- `opencv.canny`
- `opencv.clahe`
- `opencv.adjust_color`

## 步驟 3：用 `inspect` 驗證接通

```powershell
toolanything inspect
```

開啟後填入：

- `mode`：`http`
- `url`：`http://127.0.0.1:9091`

然後操作：

1. 點 `檢查連線`
2. 點 `載入工具`
3. 選 `opencv.info`
4. 隨便給一張圖片測一次

如果這一步成功，代表 MCP server、`initialize`、`tools/list`、`tools/call` 都有真的跑通。

## 步驟 4：直接跑雙協議示範腳本

```powershell
python examples/opencv_mcp_web/dual_protocol_demo.py
```

這支腳本現在會直接使用 repo 內建的 `OpenAIChatRuntime`，不需要你自己再手寫 OpenAI `tools`、tool loop 或名稱映射。

如果你要真的打 OpenAI API：

```powershell
$env:OPENAI_API_KEY='你的 API key'
python examples/opencv_mcp_web/dual_protocol_demo.py --mode live-openai --model <your-model>
```

## 步驟 5：跑 smoke test

```powershell
python examples/opencv_mcp_web/smoke_test.py
```

## 步驟 6：啟動專用 Web UI

```powershell
python examples/opencv_mcp_web/web_server.py --port 5173
```

然後用瀏覽器開：

```text
http://127.0.0.1:5173
```

## 成功標準

如果下面三條都成立，就代表這個 example 是真的通了：

1. `toolanything inspect` 能列出並呼叫 OpenCV 工具
2. 專用 Web UI 能載入工具列表並成功執行工具
3. 處理完的圖片會在結果預覽區立即更新

## 常見問題

### `toolanything` 指令不存在

```powershell
python -m toolanything.cli serve examples/opencv_mcp_web/server.py --streamable-http --host 127.0.0.1 --port 9091
```

### `cv2` 載入失敗

常見原因是同時混用了 `opencv-python` 或不相容的 NumPy wheel。

建議先檢查：

```powershell
pip show numpy opencv-python 
```

這個專案建議只保留一種 OpenCV wheel，且優先使用：

```powershell
opencv-python>=4.12.0.88
```

## 延伸閱讀

- [server.py](/D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web/server.py)
- [web_server.py](/D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web/web_server.py)
- [app.js](/D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web/web/app.js)
- [toolanything inspect](/D:/PycharmProjects/ToolAnything/src/toolanything/inspector/app.py)
