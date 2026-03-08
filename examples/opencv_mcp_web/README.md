# OpenCV MCP Web 教程

這個範例會帶你從 0 跑通一條完整鏈路：

1. 用 ToolAnything 把 OpenCV 函式包成 MCP 工具
2. 啟動本機 MCP Server
3. 用內建 MCP client 確認 server 真的有接通
4. 用專用 Web UI 實際呼叫 `opencv.info`、`opencv.resize`、`opencv.canny`、`opencv.clahe`、`opencv.adjust_color`

如果你只是想知道「這個 example 到底有沒有真的能跑」，照著這份 README 做一次就知道。

## 你會看到什麼

這個範例目前暴露的工具有：

- `opencv.info`：讀取圖片寬高與通道數
- `opencv.resize`：縮放圖片
- `opencv.canny`：邊緣偵測
- `opencv.clahe`：提升局部對比
- `opencv.adjust_color`：調整亮度、飽和度與色相

## 前置條件

請在 repo 根目錄操作。

如果你還沒有把 ToolAnything 安裝成 CLI，可以先用 PowerShell 設定：

```powershell
$env:PYTHONPATH='D:\PycharmProjects\ToolAnything\src'
```

之後把本文的 `toolanything ...` 改成：

```powershell
python -m toolanything.cli ...
```

如果你的 Web UI 會跑在 `http://127.0.0.1:5173`，建議先把允許來源也設好：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```

## 步驟 1：啟動 MCP Server

執行：

```powershell
toolanything serve examples.opencv_mcp_web.server --host 127.0.0.1 --port 9091
```

成功後，你的本機會有一個 MCP HTTP server 跑在：

```text
http://127.0.0.1:9091
```

## 步驟 2：先確認 server 真的有起來

開另一個 PowerShell 視窗，執行：

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

如果 `/health` 正常、但 `/tools` 是空的，通常表示你跑到舊程序，請先停掉舊的 9091 process 再重啟。

## 步驟 3：用內建 MCP Client 驗證接通

執行：

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

如果這一步成功，代表：

- MCP server 可連線
- `initialize` 成功
- `tools/list` 成功
- `tools/call` 成功

## 步驟 4：跑 smoke test（可選，但推薦）

如果你想快速做程式化驗證：

```powershell
python -m examples.opencv_mcp_web.smoke_test
```

這一步會直接透過 repo 內建的 inspector service 呼叫本機 MCP server。

## 步驟 5：啟動專用 Web UI

切到靜態頁目錄：

```powershell
Set-Location D:\PycharmProjects\ToolAnything\examples\opencv_mcp_web\web
python -m http.server 5173
```

然後用瀏覽器開：

```text
http://127.0.0.1:5173
```

## 步驟 6：在 Web UI 做完整驗證

建議你照這個順序做：

1. 點 `使用本機 9091`
   這個按鈕現在會自動填入 URL，並直接做連線檢查。
2. 確認左側工具列表不是空的
3. 點 `使用示範圖片`，或自己上傳一張圖片
4. 先測 `opencv.info`
5. 再測 `opencv.resize`
6. 再測 `opencv.canny`
7. 最後試 `opencv.clahe` 與 `opencv.adjust_color`

## 每個工具怎麼測

### `opencv.info`

用途：確認圖片是否有成功送進 MCP tool。  
預期：會回傳寬、高、通道數。

### `opencv.resize`

用途：確認圖片會真的被處理並更新預覽。  
建議先試：

- `width = 1024`
- `height = 1024`
- `keep_aspect_ratio = true`

### `opencv.canny`

用途：確認邊緣偵測流程正常。  
建議先試：

- `threshold1 = 50`
- `threshold2 = 150`

如果想要更多邊緣，可改成 `30 / 90`；  
如果想要更乾淨，可改成 `80 / 200`。

### `opencv.clahe`

用途：確認局部對比增強能正常執行。  
建議先試：

- `clip_limit = 2.0`
- `tile_grid_size = 8`

### `opencv.adjust_color`

用途：測顏色調整工具。  
建議先試：

- `brightness = 15`
- `saturation = 20`
- `hue_shift = 10`

## 成功標準

如果下面三條都成立，就代表這個 example 是真的通了：

1. `toolanything inspect` 能列出並呼叫 OpenCV 工具
2. 專用 Web UI 能載入工具列表並成功執行工具
3. 處理完的圖片會在結果預覽區立即更新

## 常見問題

### 問題 1：`toolanything` 指令不存在

這不是範例壞掉，而是你還沒安裝 CLI。先用：

```powershell
$env:PYTHONPATH='D:\PycharmProjects\ToolAnything\src'
python -m toolanything.cli serve examples.opencv_mcp_web.server --host 127.0.0.1 --port 9091
```

### 問題 2：Web UI 顯示已接通，但工具列表是空的

通常是你連到舊版 server process。先把舊的 9091 程序停掉，再重新啟動。

### 問題 3：Web UI 連不上 MCP server

如果 Web UI 跟 MCP server 不在同一個 origin，請確認你有設定：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```

### 問題 4：按下執行工具後沒有重新可按

這是舊版前端 bug。請重新整理頁面，並確認你跑的是最新 repo 內容。

## 延伸閱讀

- [server.py](D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web/server.py)
- [app.js](D:/PycharmProjects/ToolAnything/examples/opencv_mcp_web/web/app.js)
- [toolanything inspect](D:/PycharmProjects/ToolAnything/src/toolanything/inspector/app.py)
