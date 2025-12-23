# OpenCV MCP Web Demo

這個範例示範如何把 OpenCV 工具包裝成 MCP Server，並提供網頁端 MCP Client 進行測試。

## 功能摘要

- **opencv.info**：回傳圖片寬高與通道數
- **opencv.resize**：依照指定尺寸縮放圖片（可保持比例）
- **opencv.canny**：Canny 邊緣偵測
- **Web UI**：上傳圖片、預覽結果、顯示執行進度與工具輸出（SSE 串流）

## 本機啟動

```bash
pip install -r requirements.txt
python examples/opencv_mcp_web/server.py --host 0.0.0.0 --port 9091
```

開啟瀏覽器：`http://localhost:9091`

## 部署到 Zeabur

1. 建立 Zeabur 專案並連結此 repo。
2. 設定啟動指令：

```bash
python examples/opencv_mcp_web/server.py --host 0.0.0.0 --port $PORT
```

3. Zeabur 會自動提供對外網址，打開後即可使用 Web UI。

> 若需切換 Port，請確保 Web UI 的 MCP Server URL 與服務位址一致。
