@echo off
REM Automated Blueprint Data Update - Scheduled Task
REM This batch file is called by Windows Task Scheduler

cd /d "E:\Python Project"

REM Run the update script
"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" "E:\Python Project\update_all_blueprint_data.py"

REM Exit with the script's return code
exit /b %ERRORLEVEL%
