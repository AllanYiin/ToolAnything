# Verification

## 驗證順序

優先從便宜到昂貴：

1. 安裝驗證：wheel 已重裝、skill 已同步到對應 host 路徑。
2. import 驗證：`python -c "import toolanything; print(toolanything.__file__)"`
3. registry / `ToolManager` 驗證。
4. `doctor` 驗證 `tools/list` 與 `tools/call`。
5. 真有 transport 需求時才啟動 `serve`。
6. 需要手動觀察 transcript 時再開 `inspect`。

## 本地 bundle 驗證

先做：

```powershell
python scripts/install_local_bundle.py --host auto
python -c "import toolanything; print(toolanything.__file__)"
```

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

## 成功條件

1. `tools/list` 看得到新工具名稱與 schema。
2. `tools/call` 或本地 invoke 能拿到預期輸出。
3. 名稱、description、參數型別與副作用訊號一致。
4. 若使用 class method，不需要手動補 `cls`。
5. 若用 source-based tool，沒有多餘 wrapper 夾層。
6. 交付時能說清楚 wheel 與 skill 安裝到了哪裡。
