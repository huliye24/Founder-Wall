@echo off
chcp 65001 > nul
echo.
echo ========================================
echo    AI创业者联盟 - Notion 同步工具
echo ========================================
echo.

:: 检查 Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ 未安装 Python，请先安装
    pause
    exit /b 1
)

:: 显示选项
echo 请选择操作:
echo   [1] 双向同步 (上传 + 下载)
echo   [2] 仅上传到 Notion
echo   [3] 仅从 Notion 下载
echo   [4] 查看状态
echo   [0] 退出
echo.
set /p choice=请输入选项 (1-4): 

if "%choice%"=="1" goto sync
if "%choice%"=="2" goto upload
if "%choice%"=="3" goto download
if "%choice%"=="4" goto status
if "%choice%"=="0" goto end

:sync
echo.
echo 🔄 开始双向同步...
python sync_now.py --bidirectional
goto done

:upload
echo.
echo 📤 开始上传到 Notion...
python sync_now.py --upload
goto done

:download
echo.
echo 📥 开始从 Notion 下载...
python sync_now.py --download
goto done

:status
echo.
python sync_now.py --status
goto done

:done
echo.
pause

:end