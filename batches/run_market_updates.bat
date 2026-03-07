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
cd /d "F:\infinite-solutions"

REM Ensure logs directory exists
if not exist "F:\infinite-solutions\logs" mkdir "F:\infinite-solutions\logs"

REM Run the orchestrator script and log output
"C:\Users\chris\AppData\Local\Programs\Python\Python313\python.exe" "F:\infinite-solutions\market\run_market_updates.py" >> "F:\infinite-solutions\logs\scheduler.log" 2>&1

REM Log completion
echo ============================================================================ >> "F:\infinite-solutions\logs\scheduler.log"
echo Script completed at %date% %time% >> "F:\infinite-solutions\logs\scheduler.log"
echo ============================================================================ >> "F:\infinite-solutions\logs\scheduler.log"
echo. >> "F:\infinite-solutions\logs\scheduler.log"

echo ============================================================================
echo Market Updates Completed: %date% %time%
echo ============================================================================