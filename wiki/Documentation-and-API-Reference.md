# Documentation and API Reference

ToolAnything 現在有兩套文件來源，各自負責不同問題。這一頁的目的是避免維護者把所有內容都塞回同一種文件形式，最後兩邊一起過期。

## 文件分工

### GitHub Wiki

適合放：

- Getting Started
- 任務型 how-to
- transport 選型
- 架構解說
- 遷移與除錯

### `docs/` 與自動生成 API reference

適合放：

- Python API 參考
- 模組與類別索引
- 需要跟著 `src/toolanything` 結構一起更新的內容

## 自動生成 API reference 的來源

目前 repo 內的 API reference 由下列流程維護：

```bash
pip install -e .[docs]
python scripts/generate_api_docs.py
mkdocs build
```

重點：

- `docs/` 下面的指南文件是手寫
- `docs/reference/` 由 `scripts/generate_api_docs.py` 自動生成
- 若 `src/toolanything` 的模組結構變動，應重新產生 API docs

## 為什麼不把整份 API reference 手工搬進 Wiki

原因很實際：

- GitHub Wiki 不會自動跟著 Python 模組變動更新
- 手工維護大量 API 頁面會很快失真
- ToolAnything 的 public surface 已不小，讓 `docs/reference/` 自動生成比較合理

所以這份 Wiki 應該回答：

- 這個專案怎麼上手
- 怎麼整合
- 怎麼除錯
- 架構與邊界怎麼看

而不是手工維護每一個 class、function、module 的全量清單。

## 維護建議

每次要更新公開文件時，至少問自己兩個問題：

1. 這份內容是在回答任務與理解問題，還是在列舉 API 事實？
2. 這份內容若要跟程式碼一起演進，是人工維護比較穩，還是生成比較穩？

若答案偏向事實枚舉，請優先放回 API reference。

## 相關文件

- [Home](Home)
- [Maintaining the Wiki](Maintaining-the-Wiki)
