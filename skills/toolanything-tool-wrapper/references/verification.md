# Verification

## 驗證順序

優先從便宜到昂貴：

1. 安裝驗證：wheel 已重裝、skill 已同步到對應 host 路徑。
2. `AGENTS.md` 驗證：對應 host 的 `AGENTS.md` 已被更新，且沒有重複 marker block。
3. import 驗證：`python -c "import toolanything; print(toolanything.__file__)"`
4. registry / `ToolManager` 驗證。
5. `doctor` 驗證 `tools/list` 與 `tools/call`。
6. 真有 transport 需求時才啟動 `serve`。
7. 需要手動觀察 transcript 時再開 `inspect`。

## 本地 bundle 驗證

先做：

```powershell
python scripts/install_local_bundle.py --host auto
python -c "import toolanything; print(toolanything.__file__)"
```

再確認對應 host 的 `AGENTS.md` 已包含 ToolAnything 指示 block。

如果 `toolanything` 不在 PATH，後續 CLI 一律改用：

```powershell
python -m toolanything.cli ...
```

## 常用命令

若可執行檔已安裝：

```powershell
toolanything doctor --mode stdio --tools examples.quickstart.tools
toolanything serve examples/quickstart/tools.py --stdio
toolanything serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
toolanything inspect
```

若不確定 PATH：

```powershell
python -m toolanything.cli doctor --mode stdio --tools examples.quickstart.tools
python -m toolanything.cli serve examples/quickstart/tools.py --stdio
python -m toolanything.cli serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
python -m toolanything.cli inspect
```

## 最小本地驗證

當你只是新增 callable-backed tool，至少要做到：

```python
from toolanything.core.registry import ToolRegistry

registry = ToolRegistry.global_instance()
print([spec.name for spec in registry.list()])
print(registry.execute_tool("calculator.add", arguments={"a": 1, "b": 2}))
```

## 共用自訂工具專用 MCP server 驗證

若需求涉及 `~/.toolanything/agent-mcp/` 共用 server，至少補三個檢查：

```powershell
python -m toolanything.cli serve ~/.toolanything/agent-mcp/server.py --streamable-http --host 127.0.0.1 --port 9092
python -m toolanything.cli doctor --mode http --url http://127.0.0.1:9092
python -m toolanything.cli inspect --host 127.0.0.1 --port 9060 --no-open
```

檢查重點：

1. `http://127.0.0.1:9092/health` 可達。
2. `/mcp` 的 `tools/list` 有新工具。
3. 新工具名稱出現在同一個共用 server，而不是另一個新 port。

## 成功條件

1. `tools/list` 看得到新工具名稱與 schema。
2. `tools/call` 或本地 invoke 能拿到預期輸出。
3. 名稱、description、參數型別與副作用訊號一致。
4. 若使用 class method，不需要手動補 `cls`。
5. 若用 source-based tool，沒有多餘 wrapper 夾層。
6. 若用了共用自訂工具專用 server，能說清楚 server root、port 與自動啟動方式。
7. 交付時能說清楚 wheel、skill 與 `AGENTS.md` 安裝到了哪裡。
