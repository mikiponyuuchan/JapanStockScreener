@echo off
cd /d C:\JapanStockScreener

python tools\update_intraday_strategy_h1_low_cxv.py

if errorlevel 1 (
    echo LOW-CxV update failed.
    exit /b 1
)

echo LOW-CxV update completed.
exit /b 0
