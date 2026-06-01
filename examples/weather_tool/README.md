# Weather Tool

這個範例教你在「已安裝 `toolanything`」的前提下，建立一個可被 LLM 呼叫的天氣工具。

## 學習目標
- 以 `@tool` 定義輸入/輸出清楚的工具。
- 理解如何將工具暴露給 MCP 或 OpenAI tool calling。

## 學習路徑位置
建議在 `examples/quickstart` 之後，作為第一個實務型 API 工具範例。

## 執行

請在 repo root 執行：

```bash
python examples/weather_tool/main.py
```

## 預期輸出

輸出會先印出直接呼叫工具的結果，再印出 OpenAI function tool schema。節錄如下：

```text
{'city': 'Taipei', 'unit': 'c', 'temp': 25}
weather_query
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
