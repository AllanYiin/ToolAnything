# Vision Tools

這個範例示範如何把 YOLOv8 person detection 暴露成 ToolAnything tool，適合已經跑完 quickstart、並想理解 model-backed vision tool 的使用者。

## 學習目標

- 用 `@tool` 定義含 metadata 的影像分析工具。
- 將同一個工具透過 Streamable HTTP MCP server 暴露。
- 明確區分「可註冊工具」與「需要外部模型/影像才可完整推論」的驗證層級。

## 先決條件

- Python `>=3.10`
- 已安裝本 repo：`python -m pip install -e .`
- 完整推論需要額外安裝 `ultralytics`，並準備本機影像檔。

## 執行

列出 CLI 使用方式，不下載模型：

```bash
python examples/vision_tools/yolo_person_tool.py
```

啟動 MCP server：

```bash
python -m examples.vision_tools.server --host 127.0.0.1 --port 9093
```

有本機影像與 `ultralytics` 時執行推論：

```bash
python examples/vision_tools/yolo_person_tool.py path/to/image.jpg
```

## 預期輸出

未提供影像時會顯示：

```text
Usage: python yolo_person_tool.py <image_path>
```

成功推論時會輸出 JSON，包含 `image_path`、`count` 與 `detections`。

## 測試

這個範例的無模型 smoke check 是匯入 server 並確認 tool metadata 可列出：

```bash
pytest tests/test_examples_catalog.py -q
```

完整 YOLO 推論屬於外部模型 integration test，不放入預設 CI gate。

## 相容性

- Introduced: `0.5.0`
- Verified: Python `>=3.10`
- Status: experimental

## 授權

本 example 程式碼遵循 repo license；YOLO 模型權重與測試影像不隨 repo 發布，請依各自來源授權使用。
