# register_task.ps1 — one-time installer for the PolyfunnelCollectors scheduled task.
# Registering a task requires elevation, so run this ONCE from an ADMIN PowerShell:
#   Right-click PowerShell > "Run as administrator", then:
#   & 'C:\Users\cjmcm\OneDrive\Pictures\Documents\GitHub\VictoriaAi\polyfunnel\scripts\register_task.ps1'
#
# It creates a task that runs run_collectors.ps1 at logon and every 15 minutes
# (idempotent watchdog). Re-running this script just updates the task (-Force).
#
# Remove it later with:  Unregister-ScheduledTask -TaskName PolyfunnelCollectors -Confirm:$false

#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$ps1  = 'C:\Users\cjmcm\OneDrive\Pictures\Documents\GitHub\VictoriaAi\polyfunnel\scripts\run_collectors.ps1'
if (-not (Test-Path $ps1)) { throw "wrapper not found: $ps1" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ps1`""

$atLogon = New-ScheduledTaskTrigger -AtLogOn
$watchdog = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

# Run in the logged-on user's own interactive session (needs the OneDrive path + network).
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'PolyfunnelCollectors' -Action $action `
    -Trigger $atLogon, $watchdog -Settings $settings -Principal $principal `
    -Description 'Auto-start polyfunnel BTC collectors at logon; 15-min watchdog relaunches any that died. Idempotent (no duplicate writers).' `
    -Force | Out-Null

Write-Host "Registered scheduled task 'PolyfunnelCollectors'." -ForegroundColor Green
Get-ScheduledTask -TaskName 'PolyfunnelCollectors' | Select-Object TaskName, State | Format-Table -AutoSize
Write-Host "It will run run_collectors.ps1 at each logon and every 15 minutes."
Write-Host "Run it now (optional test): Start-ScheduledTask -TaskName PolyfunnelCollectors"
Write-Host "Disable:  schtasks /Change /TN PolyfunnelCollectors /DISABLE"
Write-Host "Remove:   Unregister-ScheduledTask -TaskName PolyfunnelCollectors -Confirm:`$false"
