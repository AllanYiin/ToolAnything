# Tool Selection（metadata 與策略化搜尋）

這條路線的目標是：**理解 metadata / constraints / strategy 如何影響工具搜尋與排序**。

## 情境目標

- 建立工具 metadata（cost / latency / category / side_effect）。
- 使用 CLI 的條件搜尋做篩選。
- 自訂策略，觀察排序差異。

## 建議步驟

1. 執行 `01_metadata_catalog.py` 建立工具目錄與 metadata。
2. 參考 `02_constraints_search.sh`，用 `toolanything search` 套用條件（max-cost、latency-budget-ms、allow-side-effects、category）。
3. 執行 `03_custom_strategy.py`，加入自訂策略並比較排序結果。

## 預期輸出（節錄）

- `toolanything search` 會列出符合條件的工具，並輸出 `cost`、`latency_hint_ms`、`side_effect` 與 `category`。
- 自訂策略範例會展示不同排序結果（例如偏好低成本或低延遲）。

## 延伸閱讀

- [`src/toolanything/core/tool_search.py`](../../src/toolanything/core/tool_search.py)
- [`src/toolanything/core/selection_strategies.py`](../../src/toolanything/core/selection_strategies.py)
- [`src/toolanything/core/metadata.py`](../../src/toolanything/core/metadata.py)
