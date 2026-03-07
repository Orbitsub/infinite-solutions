@echo off
cd /d "F:\infinite-solutions"
if not exist "F:\infinite-solutions\logs" mkdir "F:\infinite-solutions\logs"
"C:\Users\chris\AppData\Local\Programs\Python\Python313\python.exe" "F:\infinite-solutions\scripts\run_character_updates.py" >> "F:\infinite-solutions\logs\scheduler.log" 2>&1
echo Script completed at %date% %time% >> "F:\infinite-solutions\logs\scheduler.log"