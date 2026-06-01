# Finance Tools

這個範例示範在本機已安裝 `toolanything` 時，如何組合多個金融工具成一條可重用流程。

## 學習目標
- 了解多工具 pipeline 的串接方式。
- 示範如何把資料查詢與計算拆成可維護步驟。

## 學習路徑位置
建議在 `weather_tool` 後閱讀，作為多工具整合的進階教材。

## 執行

請在 repo root 執行：

```bash
python examples/finance_tools/pipeline_demo.py
```

## 預期輸出

範例會輸出換算結果，並印出 `demo` user 的 state。節錄如下：

```text
{'amount': 3250.0, 'pair': 'USD/TWD'}
```

## 測試

這個範例的 smoke check 由 catalog 測試確認路徑與命令仍存在；需要完整執行時可直接跑上方命令。

```bash
pytest tests/test_examples_catalog.py -q
```

## 相容性

- Introduced: `0.5.0`
- Verified: Python `>=3.10`
- Status: stable
