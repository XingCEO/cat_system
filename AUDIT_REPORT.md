# 專案全面審查報告 — 喵喵選股 (cat_system)

報告時間: 2026-02-26T10:36:06Z

作者: Copilot CLI（自動化審查與人工式檢閱）

---

## 一、執行範圍與方法
- 範圍：整個專案（backend、frontend、部署描述檔、Dockerfile、docker-compose.yml、CI/部署相關檔案與測試套件）。
- 方法：靜態代碼掃描（grep 關鍵字搜尋）、閱讀重要設定/程式檔案（main.py、config.py、screener、formula_parser、Dockerfile、docker-compose.yml）、檢查相依性清單（requirements.txt、package.json）、嘗試執行測試（注意：本執行環境無法完成 pytest 執行，說明見下）。

---

## 二、總結（Executive Summary）
1. 重大（Critical）問題：docker-compose.yml 含明文資料庫帳密（POSTGRES_PASSWORD / DATABASE_URL => `meow:meow123`），以及開放資料庫端口至 host（5432），在生產環境構成重大風險。必要立即移除硬編碼密碼並改用 CI/Secrets / Docker Secrets 或環境變數注入，並禁止在生產將 DB 端口暴露於外網。
2. 高風險（High）問題：篩選引擎（screener）直接在 request handler 中執行大量 Pandas 運算（load_latest_data / load_multi_day_data / apply_rule 等），在高資料量下會造成記憶體飆升與阻塞 FastAPI 事件迴圈（CPU-bound），建議改為背景工作（worker queue）或將耗時運算移出 event loop（run_in_executor / Celery / RQ）。
3. 中級風險（Medium）問題：啟動時自動執行資料同步（sync_tickers 在 lifespan 中），若外部 API 斷線或慢，會延長啟動時間並影響可用性；建議非同步排程或手動/工作佇列觸發。
4. 中低風險（Medium/Low）：Dockerfile 未建立非 root 使用者，建議建立非 root 使用者以降低容器被入侵時的衝擊；CORS 與 allow_credentials 設定需注意在生產上只允許明確來源。
5. 測試/動態掃描：repo 含 backend pytest 測試，但本環境無法執行（缺 pwsh / 無辦法安裝套件）；建議在可連網的 CI 或本地機器執行 完整測試 (pytest + coverage、npm ci + tsc + npm test) 並在 CI 加入自動安全掃描（pip-audit、safety、npm audit、semgrep、bandit）。

---

## 三、具體發現（含證據與建議修復）

### 3.1 重大（Critical）
- 問題：docker-compose.yml 包含資料庫連線與密碼（範例：DATABASE_URL=postgresql+asyncpg://meow:meow123@postgres:5432/meow_stock，POSTGRES_PASSWORD: meow123）
  - 文件與位置：`docker-compose.yml`（service: postgres, lines 40-46 / lines 11 等）
  - 風險：憑證洩漏、未經授權存取資料庫、橫向移動風險
  - 建議修復：
    - 立即移除硬編碼密碼，改為在 CI/部署平台（Render/Zeabur/GitHub Actions secrets）注入環境變數或使用 Docker secrets
    - 在 production 禁止將 DB 端口 (5432) 對外暴露；若需要內部網路存取請僅在 overlay network/私有子網中允許
    - 若憑證已被提交到 VCS，請考慮更換密碼並檢視 git 提交歷史（有需要可執行 git-secrets / truffleHog）

### 3.2 高（High）
- 問題 A：Pandas 為基礎的運算在 API 同步處理（screener.load_latest_data、load_multi_day_data、apply_rule、safe_eval_formula）
  - 位置：`backend/app/engine/screener.py`、`backend/app/engine/formula_parser.py`
  - 風險：當 ticker 數量或資料量增大時，整個 DataFrame 載入記憶體（可能為上萬筆或更多），計算在主 Event Loop 中執行會引起高延遲甚至造成整個 API 無法回應。
  - 建議修復：
    1. 將重運算移到背景 worker（Celery / RQ / Dramatiq）或在 API 層排程 pre-compute 並以快取回應
    2. 若必須在 API 中運算，使用 asyncio.to_thread / loop.run_in_executor() 將 CPU-bound 任務移至 thread/process pool
    3. 避免一次載入整表至 DataFrame，改為分批處理或在 DB 層預先聚合/計算

- 問題 B：safe_eval_formula 使用 df.eval(engine="numexpr") 並有 token 白名單
  - 位置：`backend/app/engine/formula_parser.py`（使用 token 驗證 + df.eval）
  - 風險：目前有白名單驗證，整體設計良好，但建議進一步強化：
    - 移除 '.' 作為允許運算子（若不是必要），以避免任何形式的屬性/方法存取（雖 numexpr 限制很多功能，但更保守更安全）
    - 對公式長度、複雜度（token 數量）加上上限，避免被用作 DOS

### 3.3 中（Medium）
- 問題：啟動流程會在 lifespan 中自動執行 sync_tickers（network I/O 與 DB 寫入）
  - 位置：`backend/main.py` 的 lifespan 中會呼叫 `sync_tickers()`
  - 風險：若遠端 API 慢或失敗會延後啟動；生產環境應避免在啟動流程中做大量同步操作
  - 建議：改為排程任務或手動觸發，或將其移至 background worker

- 問題：Dockerfile 沒有建立非 root 使用者
  - 位置：`backend/Dockerfile`、`Dockerfile`（多階段）
  - 建議：新增 non-root user 並使用 `USER` 指令降低容器被攻陷後的權限

- 問題：docker-compose 對 Postgres / Redis 開放 host port（開發環境易用，但 production 不應暴露）
  - 建議：使用內部網路/overlay network 或移除對 host 的 port map

### 3.4 低（Low）
- 找到的其他注意事項：
  - repo 包含 `.env.example`，使用良好，但務必不要把 `.env` 推上版本控制
  - frontend 使用 proxy 指向 `http://127.0.0.1:8000`，開發便利；建議生產使用反向代理並啟用 HTTPS

---

## 四、測試與自動化掃描 (執行情況與建議)
- 已在 repo 發現後端測試：`backend/tests/` 包含多項單元測試（test_screener.py、test_operators.py、test_data_sync.py、test_config_and_endpoints.py 等）。
- 嘗試在本環境執行 pytest 失敗，原因：執行環境缺少 pwsh（PowerShell Core）；此外，執行测试通常需安裝相依套件（pip install -r requirements.txt），而本環境無法直接下載安裝套件。
- 建議在可上網的 CI (GitHub Actions / GitLab CI) 或本地機器執行下列指令，並將其加入 CI 流程：
  - 後端（Python）：
    ```bash
    cd backend
    python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    pip install pytest pytest-cov
    pytest tests/ --cov=./ -q
    ```
  - 前端（Node）：
    ```bash
    cd frontend
    npm ci
    npm run lint
    npx tsc --noEmit
    npm run build
    ```
- 建議加入自動安全掃描：pip-audit / safety / bandit / semgrep / npm audit，並在 CI 中阻擋高風險套件

---

## 五、效能分析觀察與建議
- 觀察點：整體可能效能瓶頸集中在篩選引擎（Pandas 運算）與同步資料載入（DB → DataFrame）。
- 建議：
  1. 減少同步運算：將重度運算移至背景工作（每天/定期 pre-compute）並在 API 回應時讀取快取
  2. 若必須即時計算，改為在 DB 使用 SQL 聚合（或在 DB 層加索引）以減少資料傳輸與記憶體消耗
  3. 針對前端：使用 Vite 的 code-splitting（已配置），檢查 bundle 大小與第三方 lib（例如把大型圖表庫 lazy-load）
  4. 加入性能監控（APM）與慢查詢記錄以找出真實瓶頸

---

## 六、死碼 / 未使用程式碼偵測建議
- 方法：執行完整測試集並使用 coverage (pytest-cov)，找出 coverage 低或未觸及的模組；再進行 import-graph 或 static analysis（vulture）來標記未引用的函式/模組。
- 建議步驟：
  1. 在 dev 分支執行 `pytest --cov=app tests/` 產生 coverage report
  2. 使用 `vulture` 檢測死碼
  3. 對高風險/低確信度死碼先標記 TODO 或寫測試再移除

---

## 七、優先修復清單（建議順序）
1. 移除 docker-compose 中的明文密碼，重置 DB 密碼（Critical）
2. 禁止在 production 暴露 Postgres / Redis 的 host ports（Critical）
3. 將重運算移至 background worker 或 thread/process pool（High）
4. 將啟動時的資料同步改為排程或背景工作（High）
5. 為管理/風險端點加強認證與限制（如 /api/cache/clear）與速率限制（Medium）
6. 建立 CI：pytest、coverage、pip-audit/npm-audit、semgrep（Medium）
7. 建立非 root 的容器執行環境（Low）

---

## 八、可立即採取的修補範例（片段）

1) docker-compose: 移除硬編碼、改用 env 引入（示例）

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    # 不在生產暴露 5432
    # ports:
    #   - "5432:5432"
```

2) Dockerfile: 建立非 root user

```dockerfile
FROM python:3.12-slim
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3) Screener: 將重運算移出 event loop（簡示）

```py
from asyncio import get_running_loop

# 在 API handler 中
loop = get_running_loop()
result = await loop.run_in_executor(None, sync_heavy_function, args)

# 或使用 Celery 將 job 丟給 worker
```

---

## 九、後續建議與交付物
- 若需要，將產出完整 PDF/Markdown 報告包含更多程式碼摘錄、每項 issue 的責任人與 PR 修補示例；也可建立 GitHub Issue 與 PR 範本。
- 建議立即在 CI 中加入：
  - `python -m pip install pip-audit && pip-audit` 或 `safety check`
  - `bandit -r backend/`
  - `npm audit --audit-level=high` 並在依賴有高風險時 fail build
- 我可以：
  - (A) 生成一份更長的逐檔案檢查報告並加入修補程式碼片段
  - (B) 協助撰寫 CI workflow 範例（GitHub Actions）以自動執行測試與安全掃描

---

## 十、附錄：已檢視之檔案（節錄）
- docker-compose.yml
- backend/Dockerfile, Dockerfile
- backend/config.py, backend/main.py, backend/launcher.py
- backend/app/engine/formula_parser.py, screener.py, data_sync.py, operators.py
- backend/requirements.txt
- frontend/package.json, vite.config.ts
- backend/tests/*

---

(結束)
