# ToolAnything Docs

ToolAnything 是給 AI 開發工程師的工具層。你定義一次 tool，就可以同時接上 MCP 與 OpenAI tool calling，而不用自己維護兩套 schema、兩套路由與兩套執行迴圈。

## 從哪裡開始

- 第一次接觸這份文件：先看 [Docs Map](docs-map.md)
- 想了解整體設計：看 [Architecture Walkthrough](architecture-walkthrough.md)
- 想知道如何維護文件：看 [Build Docs](build-docs.md)
- 想看自動生成的 Python API 文件：看 [API Reference](reference/index.md)

## 這份文件站包含什麼

- 手寫指南：架構、遷移、inspect 規格與 examples 導覽
- 自動生成 API 參考：由 `scripts/generate_api_docs.py` 掃描 `src/toolanything`
- 本機建置說明：如何更新 API docs、啟動預覽站、在 CI 驗證文件

## 文件維護原則

- 概念、架構、教學路徑用手寫 Markdown
- API 參考用程式自動生成，避免 module 新增或搬移後文件失真
- 文件建置失敗應該在 CI 就被擋下，而不是等使用者點進 broken page 才發現
