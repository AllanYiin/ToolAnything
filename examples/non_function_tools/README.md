# Non-function Tools Examples

這個資料夾集中放置**非函數類工具範例**，也就是不以 `@tool` 直接包 Python function，
而是把外部來源、模型 artifact 或查詢模板直接註冊成 tool 的案例。

## 這一類範例包含什麼

- `http_tool.py`：把 HTTP endpoint 宣告成 tool。
- `sql_tool.py`：把參數化 SQL 查詢宣告成 tool。
- `onnx_tool.py`：把 ONNX model artifact 宣告成 tool。
- `pytorch_tool.py`：把 PyTorch model artifact 宣告成 tool。

## 為什麼集中收納

- 這些範例都在展示同一個概念：**工具不是只能從 Python function 來，也可以直接從 source / artifact 來。**
- 放在同一個資料夾，比散在 `examples/` 根目錄更容易理解分類，也比較好補共同文件。
- `examples/` 根目錄仍保留同名 shim，避免舊文件、測試或使用者習慣路徑直接失效。

## 執行方式

在 repo 根目錄：

```bash
python examples/non_function_tools/http_tool.py
python examples/non_function_tools/sql_tool.py
python examples/non_function_tools/onnx_tool.py
python examples/non_function_tools/pytorch_tool.py
```

SQL 範例會直接讀取隨附的 SQLite 資料庫：

```text
examples/non_function_tools/assets/analytics.sqlite
```

這樣你不只可以執行腳本，也可以直接用 DB Browser、sqlite3 CLI 或其他工具打開資料檔查看內容。

ONNX 範例也直接附上 tiny model artifact：

```text
examples/non_function_tools/assets/tiny_vad_router.onnx
```

它是一顆手工建立的單層線性 VAD router，權重與 PyTorch 範例中的 `TinyVadRouter` 相同，
用途是示範「repo 內附固定 ONNX artifact」的最小做法，而不是提供真實生產模型。

如果你還在使用舊路徑，這些 shim 仍可運作：

```bash
python examples/http_tool.py
python examples/sql_tool.py
python examples/onnx_tool.py
python examples/pytorch_tool.py
```

## 相依套件

- HTTP / SQL：基本安裝即可
- ONNX：執行範例只需要 `onnxruntime`
- PyTorch：需要 `torch`

如果你要重建 ONNX artifact，才需要 `onnx` 套件。

## ONNX Artifact 資訊

- 路徑：`examples/non_function_tools/assets/tiny_vad_router.onnx`
- 用途：示範 ONNX model tool 的最小 VAD gate
- 來源：依照 `examples/non_function_tools/pytorch_tool.py` 的線性層權重手工建立
- SHA256：`fdad9f4b0ec9e2bb84721ab0253e1f8235f518e7bd7a5ac24e895f2c871da08d`

## 如何重建 tiny ONNX

在 repo 根目錄執行：

```bash
python examples/non_function_tools/rebuild_tiny_vad_onnx.py
```

這支腳本會重新輸出 `tiny_vad_router.onnx` 並印出 SHA256。  
如果你未來真的需要較大的示範模型，再另外加 `fetch_models.py` 會比較合理；目前這顆 tiny artifact 直接附在 repo 內即可。
