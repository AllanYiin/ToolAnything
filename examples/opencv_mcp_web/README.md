# OpenCV ToolAnything Demo

這個範例示範**只需撰寫 `@tool` 函式**即可啟動 ToolAnything 伺服器，所有 MCP/傳輸層都由 ToolAnything 內部處理。

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

2. 啟動 ToolAnything 伺服器（載入工具模組）：

```bash
toolanything serve examples.opencv_mcp_web.server --host 0.0.0.0 --port 9091
```

伺服器提供 `/health`、`/tools`、`POST /invoke`、`POST /invoke/stream` 等端點。

3. （可選）啟動靜態 Web UI：

```bash
cd examples/opencv_mcp_web/web
python -m http.server 5173
```

開啟瀏覽器：`http://localhost:5173`，並在頁面上輸入 MCP Server URL（例如 `http://localhost:9091`）。

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

4. 若需 Web UI，請另外用靜態伺服器提供 `examples/opencv_mcp_web/web`，並在 UI 中填入 MCP Server URL。
