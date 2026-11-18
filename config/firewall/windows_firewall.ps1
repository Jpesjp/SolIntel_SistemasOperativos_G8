# Regla de Firewall de Windows para SolIntel (ejecutar como Administrador)
New-NetFirewallRule -DisplayName "SolIntel Web 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
Get-NetFirewallRule -DisplayName "SolIntel*" | Format-Table DisplayName, Enabled, Direction, Action
