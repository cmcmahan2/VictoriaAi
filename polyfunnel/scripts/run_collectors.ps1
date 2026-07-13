# run_collectors.ps1 — idempotent starter + watchdog for the polyfunnel collectors.
#
# Launched by the "PolyfunnelCollectors" scheduled task at logon and every 15 min.
# Idempotent by design: if a collector is already running it is LEFT ALONE (so we
# never get two writers on the same hour file); if it has died, it is relaunched.
# This is what gives auto-restart after a reboot AND recovery from a mid-run crash
# or the known RTDS server-recycle death.
#
# Stop collection: disable the task, then close the collector windows —
#   schtasks /Change /TN PolyfunnelCollectors /DISABLE
#   (re-enable with /ENABLE). Killing a window without disabling the task means the
#   watchdog relaunches it within 15 minutes.

$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\cjmcm\OneDrive\Pictures\Documents\GitHub\VictoriaAi\polyfunnel'
$py   = 'C:\Users\cjmcm\AppData\Local\Python\pythoncore-3.14-64\python.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
$log  = Join-Path $repo 'data\collect\collector_watchdog.log'

function Write-Log($m) {
    $line = "{0:yyyy-MM-ddTHH:mm:ssZ}  {1}" -f (Get-Date).ToUniversalTime(), $m
    Add-Content -Path $log -Value $line -Encoding utf8
}

function Ensure-Collector($script) {
    $proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$script*" }
    if ($proc) { Write-Log "$script already running (PID $($proc.ProcessId -join ','))"; return }
    if (-not $py) { Write-Log "ERROR python.exe not found; cannot start $script"; return }
    Start-Process -FilePath $py -ArgumentList "scripts\$script" `
        -WorkingDirectory $repo -WindowStyle Minimized
    Write-Log "started $script"
}

Ensure-Collector 'collect_updown.py'
Ensure-Collector 'collect_rtds.py'
Ensure-Collector 'collect_trades.py'
