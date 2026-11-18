# SolIntel - registra tareas programadas en Windows (ejecutar como Administrador)
# 1) Simulador IoT al iniciar sesion  2) Respaldo diario 2:15 a.m.
$raiz = (Resolve-Path "$PSScriptRoot\..\..").Path
$py = (Get-Command python).Source
Register-ScheduledTask -TaskName "SolIntel-Simulador" -Force `
  -Action (New-ScheduledTaskAction -Execute $py -Argument "src\simulador\simulador_iot.py" -WorkingDirectory $raiz) `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn)
Register-ScheduledTask -TaskName "SolIntel-Respaldo" -Force `
  -Action (New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$raiz\scripts\windows\respaldo.ps1`"") `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 2:15am)
Get-ScheduledTask -TaskName "SolIntel-*" | Format-Table TaskName, State
