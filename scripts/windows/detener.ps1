# SolIntel - detiene los procesos iniciados por iniciar.ps1
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
foreach ($p in "web", "simulador") {
  if (Test-Path "run\$p.pid") {
    $id = Get-Content "run\$p.pid"
    Stop-Process -Id $id -ErrorAction SilentlyContinue
    Remove-Item "run\$p.pid"; Write-Host "$p detenido (PID $id)"
  }
}
