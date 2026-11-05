#!/usr/bin/env python3
"""Tira um print da tela (todos os monitores) pro Ultron ver. Uso: python atalhos/tela.py

Salva em .estado/telas/tela-HHMMSS.png (reduzida pra no máximo 1920 px de largura) e imprime o caminho.
O Claude abre a imagem com a ferramenta Read. Só os 5 prints mais recentes ficam guardados.
Windows: usa o .NET pelo powershell.exe (sem instalar nada). Mac: screencapture.
"""
import subprocess
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / ".estado" / "telas"

PS = r"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DPI { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DPI]::SetProcessDPIAware() | Out-Null
$t = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $t.Width, $t.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($t.Left, $t.Top, 0, 0, $bmp.Size)
$max = 1920
if ($bmp.Width -gt $max) {
  $h = [int]($bmp.Height * $max / $bmp.Width)
  $peq = New-Object System.Drawing.Bitmap $max, $h
  $g2 = [System.Drawing.Graphics]::FromImage($peq)
  $g2.InterpolationMode = 'HighQualityBicubic'
  $g2.DrawImage($bmp, 0, 0, $max, $h)
  $bmp = $peq
}
$bmp.Save($env:DESTINO, [System.Drawing.Imaging.ImageFormat]::Png)
"""


def main():
    PASTA.mkdir(parents=True, exist_ok=True)
    destino = PASTA / f"tela-{time.strftime('%H%M%S')}.png"
    if sys.platform == "darwin":
        subprocess.run(["screencapture", "-x", str(destino)], check=True)
    else:
        import os
        env = dict(os.environ, DESTINO=str(destino))
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS],
                           env=env, capture_output=True, text=True, timeout=30)
        if not destino.exists():
            sys.exit("Não consegui tirar o print: " + (r.stderr or r.stdout).strip()[-300:])
    for velho in sorted(PASTA.glob("tela-*.png"))[:-5]:
        velho.unlink(missing_ok=True)
    print(destino)


if __name__ == "__main__":
    main()
