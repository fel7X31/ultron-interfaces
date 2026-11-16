# O que está tocando no Windows agora (Spotify, YouTube no navegador, o player do Ultron...), em JSON.
# Sem nada tocando: {}. Quem chama é o midia.py.
#   sem nada:                    mostra uma vez e sai
#   -Vigiar -Dono N [-Capa arq]: fica olhando e escreve uma linha nova a cada mudança, enquanto o processo N (o Ultron)
#                                viver. Com -Capa, salva a capa da faixa nesse arquivo e põe um número novo em "capa".
param([switch]$Vigiar, [int]$Dono = 0, [string]$Capa = '')

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

$Gerente = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
$Musica = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties, Windows.Media.Control, ContentType = WindowsRuntime]
$Fluxo = [Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType = WindowsRuntime]
$Entrada = [Windows.Storage.Streams.IInputStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
# O fluxo da capa chega como objeto do Windows que o PowerShell 5 não sabe converter: a conversão vai por reflexão.
$ParaNet = [System.IO.WindowsRuntimeStreamExtensions].GetMethod('AsStreamForRead', [type[]]@($Entrada))
$gerente = Esperar $Gerente::RequestAsync() $Gerente

$script:faixaDaCapa = ''   # título|artista da última capa salva
$script:numeroDaCapa = 0   # muda a cada capa salva (a barra usa pra buscar a imagem nova)
$script:temCapa = $false
$script:releituras = 0     # o app troca a capa um pouco depois do título: lê de novo nas próximas voltas

function Salvar-Capa($miniatura) {
    if (-not $miniatura) { return $false }
    try {
        $fluxo = Esperar ($miniatura.OpenReadAsync()) $Fluxo
        $leitor = $ParaNet.Invoke($null, @($fluxo))
        $arquivo = [System.IO.File]::Create($Capa)
        try { $leitor.CopyTo($arquivo) } finally { $arquivo.Close(); $leitor.Close() }
        return $true
    } catch { return $false }
}

function Conferir-Capa($tocando) {
    $faixa = "$($tocando.Title)|$($tocando.Artist)"
    if ($faixa -ne $script:faixaDaCapa) {
        $script:faixaDaCapa = $faixa
        $script:releituras = 2
    } elseif ($script:releituras -le 0) {
        return
    }
    $script:releituras--
    $script:temCapa = Salvar-Capa $tocando.Thumbnail
    if ($script:temCapa) { $script:numeroDaCapa++ }
}

function Tocando {
    $sessao = $gerente.GetCurrentSession()
    if (-not $sessao) { return '{}' }
    $tocando = Esperar ($sessao.TryGetMediaPropertiesAsync()) $Musica
    if ($Capa) { Conferir-Capa $tocando }
    [ordered]@{
        titulo  = $tocando.Title
        artista = $tocando.Artist
        app     = $sessao.SourceAppUserModelId
        tocando = [string]$sessao.GetPlaybackInfo().PlaybackStatus -eq 'Playing'
        capa    = $(if ($script:temCapa) { [string]$script:numeroDaCapa } else { '' })
    } | ConvertTo-Json -Compress
}

if (-not $Vigiar) { Tocando; exit }

$anterior = ''
while ($Dono -eq 0 -or (Get-Process -Id $Dono -ErrorAction SilentlyContinue)) {
    $agora = Tocando
    if ($agora -ne $anterior) {
        [Console]::Out.WriteLine($agora)
        [Console]::Out.Flush()
        $anterior = $agora
    }
    Start-Sleep -Milliseconds 1500
}
