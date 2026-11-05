# Print de todos os monitores, reduzido pra no maximo 1920 px de largura.
# Uso: powershell -File atalhos/tela.ps1 <arquivo.png>   (quem chama e o tela.py)
param([Parameter(Mandatory)] [string] $Destino)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing

# Sem isso, com zoom do Windows (125%, 150%) o print sai cortado
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DPI { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DPI]::SetProcessDPIAware() | Out-Null

$area = [System.Windows.Forms.SystemInformation]::VirtualScreen
$print = New-Object System.Drawing.Bitmap $area.Width, $area.Height
[System.Drawing.Graphics]::FromImage($print).CopyFromScreen($area.Left, $area.Top, 0, 0, $print.Size)

$max = 1920
if ($print.Width -gt $max) {
    $altura = [int]($print.Height * $max / $print.Width)
    $print = New-Object System.Drawing.Bitmap $print, $max, $altura
}
$print.Save($Destino, [System.Drawing.Imaging.ImageFormat]::Png)
