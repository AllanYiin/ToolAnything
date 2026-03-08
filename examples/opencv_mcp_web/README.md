# OpenCV ToolAnything Demo

這個範例示範如何把 OpenCV 函式包成 ToolAnything `@tool`，再自動轉成 MCP 工具並啟動 MCP HTTP server。你可以用：

- `toolanything serve examples.opencv_mcp_web.server`
- 內建 Web MCP client `toolanything inspect`
- 本範例附的影像處理 Web UI

三條路徑交叉驗證同一組工具。

## 功能摘要

- **opencv.info**：回傳圖片寬高與通道數
- **opencv.resize**：依照指定尺寸縮放圖片（可保持比例）
- **opencv.canny**：Canny 邊緣偵測
- **Web UI**：上傳圖片、預覽結果、顯示執行進度與工具輸出（SSE 串流）

## 本機啟動

1. 安裝相依套件：

```bash
pip install -r requirements.txt
```

2. 啟動 MCP server（使用既有 ToolAnything 機制載入工具模組）：

```bash
toolanything serve examples.opencv_mcp_web.server --host 127.0.0.1 --port 9091
```

伺服器會把 `opencv.info`、`opencv.resize`、`opencv.canny` 自動轉成 MCP 工具，並提供 `/health`、`/tools`、`GET /sse`、`POST /messages/{session_id}`、`POST /invoke`、`POST /invoke/stream` 等端點。

3. 用內建 MCP client 確認 server 已接通：

```bash
toolanything inspect
```

在 inspect 裡填入：

- `mode`: `http`
- `url`: `http://127.0.0.1:9091`

接著執行：

- `檢查連線`
- `載入工具`
- 手動呼叫 `opencv.info`

4. （可選）用範例附的 smoke test 直接驗證 inspect/service 可以連到這個 example：

```bash
python -m examples.opencv_mcp_web.smoke_test
```

5. 啟動範例 Web UI：

```bash
cd examples/opencv_mcp_web/web
python -m http.server 5173
```

如果你把 UI 跑在 `5173`，MCP server 需要允許這個 origin。Windows PowerShell 例子：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
toolanything serve examples.opencv_mcp_web.server --host 127.0.0.1 --port 9091
```

開啟瀏覽器：`http://127.0.0.1:5173`

Web UI 驗證建議順序：

1. 點 `檢查連線`
2. 點 `使用示範圖片`
3. 選 `opencv.info` / `opencv.resize` / `opencv.canny`
4. 點 `執行工具`

這樣可以同時確認：

- MCP server 有正常暴露 OpenCV 工具
- 內建 inspect client 可以接通與調用
- 專用 Web UI 也能正常呼叫同一組工具

## 部署到 Replit

1. 在 Replit 建立新專案，選擇 **Import from GitHub**，貼上此 repo 的網址。
2. 在 Replit 的 Shell 執行安裝：

```bash
pip install -r requirements.txt
```

3. 設定 Replit 的 **Run command**：

```bash
toolanything serve examples.opencv_mcp_web.server --host 0.0.0.0 --port 3000
```

4. 若需 Web UI，請另外用靜態伺服器提供 `examples/opencv_mcp_web/web`，並確保 `TOOLANYTHING_ALLOWED_ORIGINS` 包含該 UI 網址。
