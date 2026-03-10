# Build Docs

ToolAnything 現在同時有手寫文件與自動生成的 API reference。

## 本機建置

先安裝文件依賴：

```bash
pip install -e .[docs]
```

更新 API reference：

```bash
python scripts/generate_api_docs.py
```

建置靜態文件站：

```bash
mkdocs build
```

啟動本機預覽：

```bash
mkdocs serve
```

## 維護規則

- `docs/` 下面的指南文件用手寫方式維護
- `docs/reference/` 由 `scripts/generate_api_docs.py` 自動生成
- 如果你新增、搬移或刪除 `src/toolanything` 裡的 module，請重新跑一次 API docs 生成
- PR 至少要通過 `python scripts/generate_api_docs.py` 與 `mkdocs build`

## 為什麼這樣做

這個 repo 的手寫文件主要回答「為什麼這樣設計」與「怎麼用」，API reference 則回答「實際有哪些模組、類別與函式」。兩者混在同一套人工維護流程裡，最後通常只會有一邊過期。
