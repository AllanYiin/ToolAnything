# Tool Selection 教程

這個範例不是要你背 API，而是帶你實際看懂三件事：

1. 工具的 `metadata` 長什麼樣
2. `constraints` 怎麼把不符合條件的工具排除掉
3. `custom strategy` 怎麼在保留原本查詢語意的前提下，改變排序結果

照著下面做，你會看到同一組工具如何因為不同策略而產生不同排序。

## 你會學到什麼

- 如何替工具加上 `cost`、`latency_hint_ms`、`category`、`side_effect`
- 如何用搜尋條件只留下符合預算或分類的工具
- 如何寫一個自訂 strategy，先沿用 baseline 挑出候選，再改排序邏輯

## 前置條件

在 repo 根目錄執行以下指令。

如果你已經把 ToolAnything 安裝成 CLI，可直接用 `toolanything ...`。  
如果還沒安裝，Windows PowerShell 可以先這樣執行：

```powershell
$env:PYTHONPATH='D:\PycharmProjects\ToolAnything\src'
```

之後把 README 裡的 `toolanything ...` 改成：

```powershell
python -m toolanything.cli ...
```

## 步驟 1：先看工具目錄與 metadata

執行：

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

這一步的重點不是執行工具，而是先建立「工具可以帶有可搜尋 metadata」這個觀念。

## 步驟 2：用 constraints 篩選工具

你可以直接參考 [02_constraints_search.sh](D:/PycharmProjects/ToolAnything/examples/tool_selection/02_constraints_search.sh)，但第一次建議直接手動跑下面這些指令，比較容易理解。

### 範例 A：只看成本不超過 `0.02` 的工具

```powershell
toolanything search --max-cost 0.02
```

### 範例 B：只看延遲低於 `500ms` 的工具

```powershell
toolanything search --latency-budget-ms 500
```

### 範例 C：只看 `finance` 分類

```powershell
toolanything search --category finance
```

### 範例 D：排除有副作用的工具

```powershell
toolanything search --query catalog --category nlp
```

補充：`toolanything search` 的 `allow_side_effects` 預設就是排除高風險工具；只有你明確加上 `--allow-side-effects`，像 `catalog.send_email` 這類工具才會被納入。

## 步驟 3：比較預設策略與自訂策略

執行：

```powershell
python examples/tool_selection/03_custom_strategy.py
```

你會看到類似輸出：

```text
查詢條件：query='文件翻譯', categories=['nlp'], allow_side_effects=False

預設策略結果（相似度/失敗分數優先）：
- catalog.translate_quality: cost=0.06, latency=1800
- catalog.translate_fast: cost=0.015, latency=150

自訂策略結果（保留相同篩選，但改成成本/延遲優先）：
- catalog.translate_fast: cost=0.015, latency=150
- catalog.translate_quality: cost=0.06, latency=1800
```

這就是這個範例真正想教的知識點：

- 預設策略比較重視查詢相似度
- 自訂策略先保留 baseline 挑出的同一組候選工具，再把排序規則改成優先低成本、低延遲

也就是說，`custom strategy` 的重點不是把整套搜尋推翻重做，而是：

- 先保留原本 query / tags / prefix / constraints 的語意
- 再針對「baseline 已挑出的候選工具如何排名」做客製化

## 什麼情況適合自訂 strategy

下面幾種情境就很適合：

- 你想優先選便宜工具，再考慮品質
- 你想在高峰期優先選低延遲工具
- 你想把最近失敗率高的工具再往後排
- 你想依部門、租戶或資料區域做自訂排名

## 常見誤區

### 誤區 1：把 custom strategy 寫成另一套搜尋系統

這會讓 query、tags、constraints 的意義變得不一致，最後使用者看不懂為什麼結果會變。

### 誤區 2：只改排序，卻偷偷把 side-effect 工具加回來

如果你的 strategy 直接拿全部工具重排，可能會把本來不夠相關的工具撈回結果裡，這通常不是你想要的。

### 誤區 3：README 只講設計，不告訴使用者怎麼跑

範例文件最重要的是讓人能重現結果，所以這份 README 現在才改成步驟式教程。

## 延伸閱讀

- [tool_search.py](D:/PycharmProjects/ToolAnything/src/toolanything/core/tool_search.py)
- [selection_strategies.py](D:/PycharmProjects/ToolAnything/src/toolanything/core/selection_strategies.py)
- [metadata.py](D:/PycharmProjects/ToolAnything/src/toolanything/core/metadata.py)
