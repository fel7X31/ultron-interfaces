# Brilho da tela do notebook (monitor externo não deixa mudar por aqui). Quem chama é o sistema.py.
# Sem número: só mostra o brilho atual. Com número (0 a 100): muda e mostra.
param([int]$Nivel = -1)

if ($Nivel -ge 0) {
    Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods |
        Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{ Timeout = 1; Brightness = [byte]$Nivel } | Out-Null
}
(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object -First 1).CurrentBrightness
