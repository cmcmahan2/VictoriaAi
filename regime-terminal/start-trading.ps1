# start-trading.ps1 — launch the BTC swing dashboard + Telegram watcher (paper).
# Registered as a Task Scheduler task that runs at logon. Safe to re-run by hand:
# it stops any existing instances first, then starts fresh. Logs are written to
# server.log / alerts.log (and .err) next to this script.

$dir = "C:\Users\cjmcm\btc-dashboard\regime-terminal"
$py  = "C:\Users\cjmcm\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$env:PYTHONUTF8 = "1"

# Stop any running server/watcher so this is idempotent.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*server.py*' -or $_.CommandLine -like '*alerts.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# Dashboard server (warms the regime cache on startup).
Start-Process -FilePath $py -ArgumentList 'server.py' -WorkingDirectory $dir -WindowStyle Hidden `
  -RedirectStandardOutput "$dir\server.log" -RedirectStandardError "$dir\server.err"

# Give the server a head start before the watcher begins polling it.
Start-Sleep -Seconds 25

# Telegram alert watcher (checks every 15 min).
Start-Process -FilePath $py -ArgumentList 'alerts.py','--loop','15' -WorkingDirectory $dir -WindowStyle Hidden `
  -RedirectStandardOutput "$dir\alerts.log" -RedirectStandardError "$dir\alerts.err"
