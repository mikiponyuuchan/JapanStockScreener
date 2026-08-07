@echo off

cd /d C:\JapanStockScreener

python src\main.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo エラーが発生しました。
    echo ========================================
    pause
    exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i

start "" "results\%TODAY%_stock_result.xlsx"

exit