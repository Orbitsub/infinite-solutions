@echo off
REM Automated Blueprint Data Update - Scheduled Task
REM This batch file is called by Windows Task Scheduler

cd /d "F:\infinite-solutions"

REM Run the update script
"C:\Users\chris\AppData\Local\Programs\Python\Python313\python.exe" "F:\infinite-solutions\update_all_blueprint_data.py"

REM Exit with the script's return code
exit /b %ERRORLEVEL%
