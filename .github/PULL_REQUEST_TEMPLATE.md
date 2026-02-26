## 說明
請簡要描述本 PR 的目的與變更內容，以及為何需要這些變更。

## 變更項目
- 

## 測試
- 後端：`cd backend && pytest tests/`
- 前端：`cd frontend && npm ci && npm run build`

## 安全注意事項
- 若變更包含憑證或環境變數的處理，請確認 secrets 已建立並未直接寫入程式碼或設定檔。

## 關聯 issue
- 

## 備註
- 若需要，我可以在合併後協助檢視 GitHub Actions 的 logs 並建立後續修補清單。
<!-- PR 範本：請在建立修補 PR 時填寫以下內容 -->

## 變更說明
- 簡要描述本次變更做了什麼（1-2 行）

## 風險評估（必填）
- 是否包含敏感設定/憑證修改：是/否
- 是否會對生產資料造成影響：高/中/低

## 測試方式（必填）
- 已執行的測試指令（例如 `pytest tests/`、`npm run build`）
- 本地/CI 執行結果摘要

## 安全檢查清單（必填）
- [ ] 沒有硬編碼憑證或秘密（如 API keys、DB 密碼）
- [ ] 若為依賴升級，已檢查是否有已知漏洞（pip-audit / npm audit）
- [ ] 若修改容器/部署，已檢查 Dockerfile 不以 root 執行及不在生產暴露敏感 port

## 相關 issue / 相關 PR
- 相關 issue 編號或說明

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
