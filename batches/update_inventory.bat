@echo off
REM Auto-update LX-ZOJ Inventory
cd /d "E:\Python Project"
C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe update_lx_zoj_inventory.py >> logs\inventory_updates.log 2>&1
