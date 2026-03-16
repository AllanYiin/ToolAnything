# Verification

## 驗證順序

優先從便宜到昂貴：

1. 匯入或執行模組，確認沒有註冊期例外。
2. 直接用 registry 或 `ToolManager` 呼叫。
3. 跑 `doctor` 驗證 `tools/list` 與 `tools/call`。
4. 真有 transport 需求時才啟動 `serve`。
5. 需要手動觀察 transcript 時再開 `inspect`。

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

## 常見失敗點

1. 忘了 description，`strict=True` 下會失敗。
2. 函數簽名不清楚，導致 schema 不穩。
3. 以為 ToolAnything 只支援普通函數，錯過 class method 與 source-based API。
4. 只產 schema 沒做呼叫驗證，結果註冊成功但 runtime 失敗。
5. 修改了不相干的 transport / runtime 程式，只為了包一支新工具。
