# Import 指引

## 對外（Public API）建議

請從以下穩定入口匯入：

- `toolanything`（核心高階 API）
- `toolanything.core`（核心型別/工具）
- `toolanything.pipeline`（Pipeline 相關型別）

範例：

```python
from toolanything import ToolRegistry, ToolDefinition
from toolanything.core import render_report, parse_cmd
from toolanything.pipeline import PipelineContext
```

> 內部模組路徑可能會調整，請避免直接從子模組匯入（例如 `toolanything.core.registry`）。

## 內部（套件內）匯入規範

- 套件內部請優先使用相對匯入：`from .xxx import yyy`、`from ..core import ToolRegistry`。
- 避免在套件內部使用 `toolanything.*` 的絕對匯入，降低 package 初始化時序與循環依賴風險。

## Lazy import 與 TYPE_CHECKING

- 對外 re-export 採 lazy import（`__getattr__`），減少啟動時的負擔與循環依賴。
- 需要給型別檢查器的符號，請放在 `if TYPE_CHECKING:` 區塊中。

## IDE / Pyright 設定

本專案為 src-layout，建議：

- 使用 `pyrightconfig.json`（已加入 `include: ["src"]`, `extraPaths: ["src"]`）。
- 開發時使用 editable install：

```bash
python -m pip install -e ".[dev]"
```

這樣 IDE 與 pyright 能正確解析 `toolanything` 的匯入。
