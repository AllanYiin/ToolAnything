# Tool Selection 教程

這組範例的目的是讓你實際看懂三件事：

1. 工具的 `metadata` 長什麼樣
2. `constraints` 怎麼把不符合條件的工具排除掉
3. `custom strategy` 怎麼在保留原本查詢語意的前提下改變排序結果

以下命令以「你已安裝 `toolanything` 套件，且工作目錄在 repo 根目錄」為前提。

## 步驟 1：先看工具目錄與 metadata

```powershell
python examples/tool_selection/01_metadata_catalog.py
```

你會看到類似輸出：

```text
已建立工具目錄：
- catalog.summarize (cost=0.02, latency=800, side_effect=False, category=nlp)
- catalog.translate_quality (cost=0.06, latency=1800, side_effect=False, category=nlp)
- catalog.translate_fast (cost=0.015, latency=150, side_effect=False, category=nlp)
- catalog.send_email (cost=0.1, latency=300, side_effect=True, category=ops)
- catalog.calculate_tax (cost=0.01, latency=60, side_effect=False, category=finance)
```

## 步驟 2：用 constraints 篩選工具

```powershell
python examples/tool_selection/02_constraints_search.py
```

這一步會示範：

- `max_cost`
- `latency_budget_ms`
- `allow_side_effects=False`
- `categories=["finance"]`

## 步驟 3：比較預設策略與自訂策略

```powershell
python examples/tool_selection/03_custom_strategy.py
```

你會看到預設策略與自訂策略在相同 constraints 下得到不同排序。

## BFCL / BFCL-CN retrieval benchmark

### 一鍵 pipeline

```powershell
python -m examples.tool_selection.bfcl_pipeline `
  --workdir path\to\bfcl_run `
  --input path\to\bfcl_eval.json `
  --split eval `
  --backend fake `
  --profile full `
  --tool-doc-langs en,zh `
  --lexical-weight 0
```

### 匯出 Hugging Face dataset

```powershell
python -m examples.tool_selection.hf_dataset_exporter `
  --dataset-id gorilla-llm/Berkeley-Function-Calling-Leaderboard `
  --repo-file BFCL_v3_simple.json `
  --output path\to\bfcl_eval.json `
  --limit 200
```

如果你要拿去給 Excel / Power Query 看，請優先用 `.json`，不要用 `.jsonl`。

### 轉成 retrieval JSON

```powershell
python -m examples.tool_selection.bfcl_converter `
  --input path\to\bfcl_eval.json `
  --output path\to\bfcl_retrieval.json `
  --split eval
```

### 跑 semantic benchmark

```powershell
python -m examples.tool_selection.semantic_benchmark `
  --backend fake `
  --dataset json `
  --dataset-path path\to\bfcl_retrieval.json `
  --split eval `
  --profile full `
  --tool-doc-langs en,zh `
  --lexical-weight 0
```

## 延伸閱讀

- [catalog_shared.py](/D:/PycharmProjects/ToolAnything/examples/tool_selection/catalog_shared.py)
- [custom_strategy.py](/D:/PycharmProjects/ToolAnything/examples/tool_selection/custom_strategy.py)
- [semantic_benchmark.py](/D:/PycharmProjects/ToolAnything/examples/tool_selection/semantic_benchmark.py)
- [tool_search.py](/D:/PycharmProjects/ToolAnything/src/toolanything/core/tool_search.py)
