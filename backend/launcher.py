"""
貓星人賺大錢 - Windows EXE 啟動器
PyInstaller 打包用的入口點
"""
import os
import sys
import time
import threading
import webbrowser
import socket
import uvicorn
import logging

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 取得執行檔所在目錄（PyInstaller 打包後的路徑）
if getattr(sys, 'frozen', False):
    # 打包後的執行檔
    BASE_DIR = os.path.dirname(sys.executable)
    # PyInstaller 解壓的臨時目錄
    BUNDLE_DIR = sys._MEIPASS
else:
    # 開發模式
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# 設定工作目錄為執行檔所在位置（讓資料庫建在正確位置）
os.chdir(BASE_DIR)

# 設定環境變數
os.environ['DATABASE_URL'] = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'twse_filter.db')}"
os.environ['CORS_ORIGINS'] = "http://localhost:8000,http://127.0.0.1:8000"

PORT = 8000
HOST = "127.0.0.1"


def find_free_port(start_port=8000, max_attempts=10):
    """尋找可用的 port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((HOST, port))
                return port
        except OSError:
            continue
    return start_port


def wait_for_server(port, timeout=30):
    """等待伺服器啟動完成"""
    import urllib.request
    import urllib.error

    url = f"http://{HOST}:{port}/api/health"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            pass
        time.sleep(0.5)

    return False


def run_server(port):
    """執行 uvicorn 伺服器"""
    try:
        uvicorn.run(
            "main:app",
            host=HOST,
            port=port,
            log_level="info",
            access_log=False
        )
    except Exception as e:
        logger.error(f"伺服器錯誤: {e}")


def main():
    """主程式"""
    print("=" * 50)
    print("  貓星人賺大錢 - 台股篩選系統")
    print("=" * 50)
    print()

    # 找可用的 port
    port = find_free_port(PORT)
    if port != PORT:
        print(f"Port {PORT} 已被占用，改用 Port {port}")

    print(f"正在啟動伺服器...")
    print(f"資料庫位置: {os.path.join(BASE_DIR, 'twse_filter.db')}")
    print()

    # 在背景執行緒啟動伺服器
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # 等待伺服器就緒
    print("等待伺服器就緒...")
    if wait_for_server(port):
        url = f"http://{HOST}:{port}"
        print()
        print(f"✓ 伺服器已啟動!")
        print(f"✓ 網址: {url}")
        print()
        print("正在開啟瀏覽器...")
        webbrowser.open(url)
        print()
        print("-" * 50)
        print("請勿關閉此視窗！關閉視窗將會停止服務。")
        print("按 Ctrl+C 可以結束程式。")
        print("-" * 50)
    else:
        print("✗ 伺服器啟動失敗，請檢查錯誤訊息")
        input("按 Enter 結束...")
        return

    # 保持程式運行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在關閉...")


if __name__ == "__main__":
    main()
