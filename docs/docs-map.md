# docs 索引

- [Docs Home](index.md)：文件站首頁，先看文件定位、閱讀順序與維護原則。
- [Build Docs](build-docs.md)：本機生成 API reference、建置與預覽文件站的步驟。
- [Architecture Walkthrough](architecture-walkthrough.md)：架構動機、協議邊界、擴充方式與端到端流程。
- `examples/quickstart/README.md`：可直接執行的最小流程（註冊工具、啟動伺服器、tools/list、tools/call、工具搜尋）。
- `examples/tool_selection/README.md`：metadata / constraints / strategy 的搜尋示範。
- `examples/protocol_boundary/README.md`：protocol/core 與 server/transport 邊界對照。
- `README.md` 的 Connection Tester / Doctor 段落：快速驗證 transport、initialize、tools/list、tools/call。
- `README.md` 的 Built-in MCP Test Client 段落：Web 版互動式 inspect 介面，支援工具探索與 OpenAI tool-calling smoke test。
- [MCP Test Client Spec](mcp-test-client-spec.md)：內建 inspect 功能的規格、MVP 邊界與開發階段紀錄。
- [Migration Guide](migration-guide.md)：callable-first 舊用法、source-based 新用法與 compatibility layer 說明。
- [API Reference](reference/index.md)：由 `scripts/generate_api_docs.py` 自動生成的 Python API 參考。
- [Imports Map](IMPORTS.md)：套件匯入結構與公開介面的整理。
- [Refactor: Callable Coupling Baseline](refactor/callable-coupling-baseline.md)：invoker-first 重構前的 callable-first 耦合盤點與風險邊界。
- [Refactor: Migration Baseline](refactor/migration-baseline.md)：Phase 0 相容承諾、compatibility layer 定位與後續 phase 邊界。
