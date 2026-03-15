# Maintaining the Wiki

這一頁是給維護者看的。重點不是介紹 ToolAnything 功能，而是說明 GitHub Wiki 的交付方式、同步流程與目前專案狀態。

## 目前狀態

在撰寫這份文件時，`https://github.com/AllanYiin/ToolAnything.wiki.git` 尚不可存取，`git ls-remote` 回傳 `Repository not found`。實務上這通常表示下列其中一種情況：

- GitHub repository 尚未啟用 Wiki
- Wiki 尚未建立首頁，因此對外的 wiki repo 還不存在

所以目前 `wiki/` 目錄應視為「待同步到 GitHub Wiki 的來源」。

## GitHub Wiki 的幾個事實

根據 GitHub 官方文件：

- 每個 GitHub Wiki 本身是一個獨立 Git repository
- Wiki 的預設分支內容才會顯示在線上
- `_Sidebar.md` 與 `_Footer.md` 可用來自訂導覽

這也是為什麼這裡採用 `Home.md` 與 `_Sidebar.md` 的頁面結構。

## 初始化建議流程

1. 先到 GitHub repo 啟用 Wiki
2. 建立至少一頁首頁，讓 wiki repo 真正存在
3. 再把這個 `wiki/` 目錄的內容同步到 `ToolAnything.wiki.git`

同步範例：

```bash
git clone https://github.com/AllanYiin/ToolAnything.wiki.git
cd ToolAnything.wiki
```

之後把 `wiki/` 內的頁面複製進來，再 commit / push。

## 建議維護節奏

每次有公開功能變動時，依序檢查：

1. `README.md`
2. `docs/`
3. `examples/`
4. `src/toolanything/cli.py`
5. `src/toolanything/openai_runtime.py`
6. 這份 `wiki/`

原因：

- README 常是第一個暴露產品定位變化的地方
- `examples/` 會揭露真實可執行流程是否已變
- CLI 與 runtime 的 public surface 通常最容易讓文件過期

## 發布前檢查

在同步 Wiki 前，至少做這些事：

```bash
pip install -e .[docs]
python scripts/generate_api_docs.py
mkdocs build
```

另外，建議再跑一次：

```bash
$env:PYTHONPATH='src'; python -m toolanything.cli --help
$env:PYTHONPATH='src'; python -m toolanything.cli doctor --help
$env:PYTHONPATH='src'; python -m toolanything.cli search --help
```

這能快速檢查 CLI 參考頁是否仍然正確。

## 哪些內容不該放進 Wiki

- 大量自動生成的 API reference
- 只對內部重構階段有意義的中間筆記
- 沒有證據支持的未來功能敘述

## 相關文件

- [Documentation and API Reference](Documentation-and-API-Reference)
- [Home](Home)
