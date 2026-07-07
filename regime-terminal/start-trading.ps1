# start-trading.ps1 — launch BOTH dashboards (+ Telegram watchers) at logon.
#   • BTC swing dashboard      → http://localhost:5000   (regime-terminal)
#   • Stock Hunter dashboard   → http://localhost:5001   (stock-hunter)
# Registered as a Startup task. Safe to re-run by hand: it stops any existing
# instances first, then starts fresh. Logs are written next to each script.

$btc   = "C:\Users\cjmcm\btc-dashboard\regime-terminal"
$stock = "C:\Users\cjmcm\btc-dashboard\stock-hunter"
$py    = "C:\Users\cjmcm\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$env:PYTHONUTF8 = "1"

# Stop any running servers/watchers (both projects use server.py / alerts.py).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*server.py*' -or $_.CommandLine -like '*alerts.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

function Launch($dir, $argList, $log) {
  Start-Process -FilePath $py -ArgumentList $argList -WorkingDirectory $dir -WindowStyle Hidden `
    -RedirectStandardOutput "$dir\$log.log" -RedirectStandardError "$dir\$log.err"
}

# --- BTC swing dashboard (port 5000) + its 15-min paper alert watcher ---
Launch $btc 'server.py' 'server'
Start-Sleep -Seconds 25                        # let the regime cache warm before the watcher polls
Launch $btc @('alerts.py', '--loop', '15') 'alerts'

# --- Stock Hunter dashboard (port 5001) + its daily new-pick alert watcher ---
Launch $stock 'server.py' 'server'
Launch $stock @('alerts.py', '--loop', '24') 'alerts'
