@echo off
chcp 65001 >nul
echo ========================================
echo   貓星人賺大錢 - EXE 打包腳本
echo ========================================
echo.

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.10+
    pause
    exit /b 1
)

:: 建立虛擬環境
if not exist "venv" (
    echo [1/4] 建立虛擬環境...
    python -m venv venv
)

:: 啟用虛擬環境
echo [2/4] 啟用虛擬環境...
call venv\Scripts\activate.bat

:: 安裝依賴
echo [3/4] 安裝依賴套件...
pip install -r requirements.txt
pip install pyinstaller

:: 確保 static 資料夾存在
if not exist "static\index.html" (
    echo [錯誤] 找不到 static\index.html
    echo 請先在 frontend 目錄執行 npm run build
    echo 然後將 frontend\dist 的內容複製到 backend\static
    pause
    exit /b 1
)

:: 執行打包
echo [4/4] 執行 PyInstaller 打包...
pyinstaller app.spec --clean

echo.
echo ========================================
if exist "dist\貓星人賺大錢.exe" (
    echo [成功] 打包完成！
    echo 執行檔位置: dist\貓星人賺大錢.exe
    echo.
    echo 你可以將這個 exe 檔分享給其他人使用
) else (
    echo [失敗] 打包失敗，請檢查上方錯誤訊息
)
echo ========================================
pause
