部署說明
===========

這份說明說明如何透過 GitHub Actions 自動建立 Docker 映像並推到 GitHub Container Registry (GHCR)，以及如何連接 Zeabur 部署。

必要前置條件
- 在 GitHub repository 中啟用 Actions。
- 若要推到 GHCR：使用 workflow 內建的 `GITHUB_TOKEN`（已在 workflow 設定 `packages: write` 權限）。

欲設定的 GitHub Secrets（選項）：
- `ZEABUR_TOKEN` — 可選，若要由 Actions 直接觸發 Zeabur API（本專案未自動呼叫，請改於 Zeabur UI 建立自動拉取或手動使用）。
- `ZEABUR_SERVICE_ID` — Zeabur 服務 ID（若你要在 workflow 中加入自動觸發步驟時使用）。

工作流程摘要
- 檔案：`.github/workflows/ci-build-publish.yml`
- 觸發：push 到 `main`
- 動作：build Docker 映像、推到 `ghcr.io/<your-org>/cat-system:latest` 以及 `:sha` tag

Zeabur 部署建議
1. 在 Zeabur 建立一個 Service（或使用既有的），設定來源為 Container Registry，並填寫 GHCR 的映像位置，例如 `ghcr.io/<YOUR_ACCOUNT>/cat-system:latest`。
2. 在 Zeabur UI 中連結 GitHub 或設定自動拉取映像的頻率。
3. 若你想要由 Actions 直接觸發 Zeabur 部署，可以把 `ZEABUR_TOKEN` 與 `ZEABUR_SERVICE_ID` 加到 Secrets，並把 workflow 中補充對應的 `curl` 步驟（注意：請確認 Zeabur API 路徑與授權方式）。

如需我幫你把 Zeabur 自動觸發步驟也加入 workflow，請提供 `ZEABUR_TOKEN` 與 `ZEABUR_SERVICE_ID`（或允許我新增安全的 deploy 步驟草案）。
