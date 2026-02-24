@echo off
cd /d "E:\Python Project"
if not exist "E:\Python Project\logs" mkdir "E:\Python Project\logs"
"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" "E:\Python Project\scripts\run_character_updates.py" >> "E:\Python Project\logs\scheduler.log" 2>&1
echo Script completed at %date% %time% >> "E:\Python Project\logs\scheduler.log"