# SolIntel - monitoreo en Windows: SO, CPU, memoria, disco, procesos, puertos y salud del servicio
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
New-Item -ItemType Directory -Force -Path evidencias\monitoreo | Out-Null
$salida = "evidencias\monitoreo\monitoreo_win_$(Get-Date -Format yyyyMMdd_HHmmss).txt"
$puerto = if ($env:SOLINTEL_PUERTO) { $env:SOLINTEL_PUERTO } else { 8080 }
& {
  "=== SolIntel - Monitoreo $(Get-Date) en $env:COMPUTERNAME ==="
  "`n--- Sistema operativo"; (Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, LastBootUpTime | Format-List | Out-String).Trim()
  "`n--- CPU (% de uso)"; (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
  "`n--- Memoria"; $os = Get-CimInstance Win32_OperatingSystem
  "Total: {0:N1} GB  Libre: {1:N1} GB" -f ($os.TotalVisibleMemorySize/1MB), ($os.FreePhysicalMemory/1MB)
  "`n--- Disco"; Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n="Usado(GB)";e={[math]::Round($_.Used/1GB,1)}}, @{n="Libre(GB)";e={[math]::Round($_.Free/1GB,1)}} | Format-Table | Out-String
  "--- Procesos Python (SolIntel)"
  Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object CommandLine -match "servidor.py|simulador_iot.py" |
    Select-Object ProcessId, ParentProcessId, ThreadCount, @{n="MemMB";e={[math]::Round($_.WorkingSetSize/1MB,1)}}, CommandLine | Format-Table -AutoSize | Out-String -Width 200
  "--- Puerto $puerto"; Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue | Format-Table LocalAddress, LocalPort, State, OwningProcess | Out-String
  "--- Salud del servicio"; try { Invoke-RestMethod "http://localhost:$puerto/api/salud" | ConvertTo-Json } catch { "Servicio no responde" }
  "`n--- Auditoria"
  if (Test-Path logs\solintel.log) {
    "Login correctos: " + (Select-String -Path logs\solintel.log -Pattern "login_ok").Count
    "Login fallidos:  " + (Select-String -Path logs\solintel.log -Pattern "login_fallido").Count
  }
} | Out-File -Encoding utf8 $salida
Get-Content $salida; "Reporte: $salida"
