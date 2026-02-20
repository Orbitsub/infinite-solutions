@echo off
chcp 65001 > nul
REM ============================================================================
REM Quick Update Script for GitHub Pages
REM ============================================================================
REM After editing index.html, double-click this file to push changes live.
REM Your page will update at: https://hamektok.github.io/infinite-solutions/
REM ============================================================================

echo ============================================================================
echo Updating GitHub Pages...
echo ============================================================================
echo.

cd /d "E:\Python Project"

REM Regenerate buyback data from database
echo Regenerating buyback data...
"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" generate_buyback_data.py
echo.

REM Add and commit changes directly on main
git add index.html buyback_data.js
git commit -m "Update site data - %date% %time%"

if %errorlevel% equ 0 (
    echo.
    echo Commit successful! Pushing to GitHub...
    echo.

    git push origin main

    if %errorlevel% equ 0 (
        echo.
        echo ============================================================================
        echo SUCCESS! Your page is updating now.
        echo.
        echo Live URL: https://hamektok.github.io/infinite-solutions/
        echo Wait 1-2 minutes, then refresh the page to see changes.
        echo ============================================================================
    ) else (
        echo.
        echo ============================================================================
        echo ERROR: Push failed. Check your internet connection.
        echo ============================================================================
    )
) else (
    echo.
    echo ============================================================================
    echo No changes detected in index.html or buyback_data.js
    echo ============================================================================
)

echo.
pause
