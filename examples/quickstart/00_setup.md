# 00_setup — 安裝 / 啟動 / 驗證清單

> 目標：讓第一次使用的人可以從 0 開始跑通 Quickstart。

## 1) 建立虛擬環境並安裝

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## 2) 確認 CLI 可用

```bash
python -m toolanything.cli --help
```

## 3) 下一步順序（照著走）

1. **定義工具**：`python examples/quickstart/01_define_tools.py`（僅示範匯入與註冊）
2. **啟動 transport**：`python examples/quickstart/02_run_server.py`
3. **搜尋與呼叫**：`python examples/quickstart/03_search_and_call.py`

> 建議把 02、03 放在不同終端機：一個保持 server 連線，另一個做呼叫與搜尋。
