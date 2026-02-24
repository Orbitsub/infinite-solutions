@echo off
chcp 65001 > nul
REM ============================================================================
REM Market Updates Batch File - Zero Downtime Edition
REM ============================================================================
REM This batch file runs all market data updates in sequence.
REM All scripts use temporary tables so your production data stays accessible
REM throughout the entire 30-60 minute update process.
REM 
REM Scheduled to run every hour via Windows Task Scheduler.
REM ============================================================================

echo ============================================================================
echo Market Updates Starting: %date% %time%
echo ============================================================================

REM Change to project directory
cd /d "E:\Python Project"

REM Ensure logs directory exists
if not exist "E:\Python Project\logs" mkdir "E:\Python Project\logs"

REM Run the orchestrator script and log output
"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" "E:\Python Project\scripts\run_market_updates.py" >> "E:\Python Project\logs\scheduler.log" 2>&1

REM Log completion
echo ============================================================================ >> "E:\Python Project\logs\scheduler.log"
echo Script completed at %date% %time% >> "E:\Python Project\logs\scheduler.log"
echo ============================================================================ >> "E:\Python Project\logs\scheduler.log"
echo. >> "E:\Python Project\logs\scheduler.log"

echo ============================================================================
echo Market Updates Completed: %date% %time%
echo ============================================================================