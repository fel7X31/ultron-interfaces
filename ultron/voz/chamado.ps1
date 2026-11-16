# Ouve o microfone e escreve uma linha "ultron <confiança> <certeza 0 a 1> <segundos>" cada vez que alguém chama o
# Ultron pelo nome. Usa o reconhecimento de fala do próprio Windows (pt-BR) com uma lista fechada de frases: roda no
# PC, sem internet, e nada do áudio sai daqui. Quem chama é o chamado.py; o script para quando o processo -Dono fecha.
param([int]$Dono = 0)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime

# As funções do Windows aqui são assíncronas: AsTask transforma em algo que o PowerShell sabe esperar.
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1

function Esperar($operacao, $tipo) {
    $tarefa = $asTask.MakeGenericMethod($tipo).Invoke($null, @($operacao))
    $tarefa.Wait(-1) | Out-Null
    $tarefa.Result
}

function Escrever($linha) {
    [Console]::Out.WriteLine($linha)
    [Console]::Out.Flush()
}

function Dono-Vivo {
    $Dono -eq 0 -or [bool](Get-Process -Id $Dono -ErrorAction SilentlyContinue)
}

$Reconhecedor = [Windows.Media.SpeechRecognition.SpeechRecognizer, Windows.Media.SpeechRecognition, ContentType = WindowsRuntime]
$Lista = [Windows.Media.SpeechRecognition.SpeechRecognitionListConstraint, Windows.Media.SpeechRecognition, ContentType = WindowsRuntime]
$Restricao = [Windows.Media.SpeechRecognition.ISpeechRecognitionConstraint, Windows.Media.SpeechRecognition, ContentType = WindowsRuntime]
$Compilacao = [Windows.Media.SpeechRecognition.SpeechRecognitionCompilationResult, Windows.Media.SpeechRecognition, ContentType = WindowsRuntime]
$Resultado = [Windows.Media.SpeechRecognition.SpeechRecognitionResult, Windows.Media.SpeechRecognition, ContentType = WindowsRuntime]
$Idioma = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$Numeros = [Globalization.CultureInfo]::InvariantCulture

# Só ASCII no arquivo (o PowerShell 5 lê o .ps1 no código de página do Windows): o Ú vai pelo código dele.
# "Últron" e "Ultrom" são o jeito que se fala aqui; "Ultron" sozinho o Windows lê com a tônica no fim.
$NOMES = @('Ultron', 'Ultrom', ([string][char]0xDA + 'ltron'))
$FRASES = [string[]]@(foreach ($antes in @('', 'Ei ', 'Oi ', 'O ', 'Fala ', 'E ai ')) { foreach ($nome in $NOMES) { $antes + $nome } })

$ouvido = $Reconhecedor::new($Idioma::new('pt-BR'))
# Constraints é uma lista do Windows que o PowerShell 5 não sabe chamar direto: o Add vai por reflexão.
$adicionar = [System.Collections.Generic.ICollection``1].MakeGenericType($Restricao).GetMethod('Add')
$adicionar.Invoke($ouvido.Constraints, @($Lista::new($FRASES, 'chamado'))) | Out-Null
$compilou = Esperar ($ouvido.CompileConstraintsAsync()) $Compilacao
if ("$($compilou.Status)" -ne 'Success') {
    Escrever "erro o Windows nao montou a lista de frases ($($compilou.Status))"
    exit 1
}
$ouvido.Timeouts.InitialSilenceTimeout = [TimeSpan]::FromSeconds(30)
$ouvido.Timeouts.BabbleTimeout = [TimeSpan]::FromSeconds(4)  # falatório que não é o nome: desiste e recomeça

Escrever 'pronto'
while (Dono-Vivo) {
    try {
        $ouviu = Esperar ($ouvido.RecognizeAsync()) $Resultado
    } catch {
        Escrever ("erro " + $_.Exception.GetBaseException().Message)
        Start-Sleep -Seconds 3
        continue
    }
    if ($ouviu.Text) {  # inclusive Rejected: quem decide o que vale é o palmas.py (e o --testar-chamado mostra tudo)
        Escrever ([string]::Format($Numeros, 'ultron {0} {1:0.00} {2:0.00}', $ouviu.Confidence, $ouviu.RawConfidence,
                                   $ouviu.PhraseDuration.TotalSeconds))
    }
}
