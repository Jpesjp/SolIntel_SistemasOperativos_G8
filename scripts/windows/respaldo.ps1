# SolIntel - respaldo de datos (ZIP + SHA-256), conserva los ultimos 7
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
New-Item -ItemType Directory -Force -Path respaldos | Out-Null
$zip = "respaldos\solintel_datos_$(Get-Date -Format yyyyMMdd_HHmmss).zip"
Compress-Archive -Path data, config -DestinationPath $zip
(Get-FileHash $zip -Algorithm SHA256).Hash | Set-Content "$zip.sha256"
Get-ChildItem respaldos\*.zip | Sort-Object LastWriteTime -Descending | Select-Object -Skip 7 | ForEach-Object { Remove-Item $_, "$_.sha256" }
Write-Host "Respaldo creado: $zip"
