#!/bin/bash
echo "🚀 正在切換至極速生產模式..."

# 1. 清理舊進程
echo "🧹 清理舊有服務..."
pkill ngrok || true
pkill -f "uvicorn main:app" || true
pkill -f "vite" || true

# 2. 檢查前端構建
if [ ! -d "frontend/dist" ]; then
    echo "🏗️  正在構建前端靜態檔案..."
    cd frontend && npm run build && cd ..
fi

# 3. 啟動後端 (同時服務前端檔案)
echo "🔥 啟動高效能後端服務 (Port 8000)..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ 後端已在後台啟動 (PID: $BACKEND_PID)"

# 等待後端啟動
sleep 3

# 4. 啟動 Ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌未找到 ngrok，請先安裝"
    exit 1
fi

echo "🌐 正在啟動全球加速通道 (Port 8000)..."
echo "---------------------------------------------------"

# 啟動 ngrok
ngrok http 8000
