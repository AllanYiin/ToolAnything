# MCP Server Demo

這個範例示範「已安裝 `toolanything` 套件」後，如何用最小程式碼啟動 MCP server，並由 client 呼叫工具。

## 學習目標
- 了解 server 與 client 的最小互動流程。
- 練習把工具定義與啟動流程拆成可閱讀的教學程式。

## 學習路徑位置
建議在 `examples/quickstart` 後閱讀，作為進入跨程序呼叫前的第一個 server 範例。

## 執行

請在 repo root 執行 dummy client；client 會自動挑選空 port、啟動 server、列出工具並呼叫 `echo.text`：

```bash
python examples/mcp_server_demo/client.py
```

若要手動啟動 server：

```bash
python examples/mcp_server_demo/server.py --host 127.0.0.1 --port 9090
```

## 預期輸出

成功時會看到健康檢查、工具列表與 invoke 結果。節錄如下：

```text
[dummy client] Server is ready
echo.text
Hello MCP
```

## 測試

這個範例的 smoke check 由 catalog 測試確認路徑與命令仍存在；跨程序行為可直接跑 dummy client 驗證。

```bash
pytest tests/test_examples_catalog.py -q
python examples/mcp_server_demo/client.py
```

## 相容性

- Introduced: `0.5.0`
- Verified: Python `>=3.10` on Windows spawn multiprocessing
- Status: stable
