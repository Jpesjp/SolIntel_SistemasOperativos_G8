# SolIntel - inicia servidor web y simulador IoT en Windows 10/11 (PowerShell)
# Uso: powershell -ExecutionPolicy Bypass -File scripts\windows\iniciar.ps1
$raiz = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $raiz
New-Item -ItemType Directory -Force -Path logs, run | Out-Null
$puerto = if ($env:SOLINTEL_PUERTO) { $env:SOLINTEL_PUERTO } else { 8080 }
$sim = Start-Process python -ArgumentList "src\simulador\simulador_iot.py" -WindowStyle Hidden -PassThru `
       -RedirectStandardOutput logs\simulador.out -RedirectStandardError logs\simulador.err
$web = Start-Process python -ArgumentList "src\backend\servidor.py --puerto $puerto" -WindowStyle Hidden -PassThru `
       -RedirectStandardOutput logs\web.out -RedirectStandardError logs\web.err
$sim.Id | Set-Content run\simulador.pid
$web.Id | Set-Content run\web.pid
Start-Sleep 3
Write-Host "Servidor PID $($web.Id) | Simulador PID $($sim.Id)"
Invoke-RestMethod "http://localhost:$puerto/api/salud" | Format-List
Start-Process "http://localhost:$puerto"
