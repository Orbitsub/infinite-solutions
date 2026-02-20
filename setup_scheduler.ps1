# PowerShell script to create Windows Task Scheduler task
# Run this as Administrator to set up the daily blueprint update

$TaskName = "EVE Blueprint Data Update"
$TaskDescription = "Daily update of EVE Online blueprint data, research jobs, and web page"
$ScriptPath = "E:\Python Project\update_blueprints_scheduled.bat"
$TaskTime = "03:00AM"  # Run at 3 AM daily

Write-Host "Setting up Windows Task Scheduler task..." -ForegroundColor Cyan
Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
Write-Host "Schedule: Daily at $TaskTime" -ForegroundColor Yellow
Write-Host ""

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    Write-Host "Task '$TaskName' already exists. Removing old task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the scheduled task action
$Action = New-ScheduledTaskAction -Execute $ScriptPath

# Create the trigger (daily at specified time)
$Trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Create the principal (run whether user is logged on or not)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force

    Write-Host ""
    Write-Host "SUCCESS! Task created successfully." -ForegroundColor Green
    Write-Host ""
    Write-Host "The task will run daily at $TaskTime" -ForegroundColor Cyan
    Write-Host "You can view/modify it in Task Scheduler (taskschd.msc)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To test the task manually, run:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure you're running PowerShell as Administrator!" -ForegroundColor Yellow
    exit 1
}
