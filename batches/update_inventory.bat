@echo off
REM Auto-update LX-ZOJ Inventory
cd /d "F:\infinite-solutions"
C:\Users\chris\AppData\Local\Programs\Python\Python313\python.exe update_lx_zoj_inventory.py >> logs\inventory_updates.log 2>&1
