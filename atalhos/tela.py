#!/usr/bin/env python3
"""Tira um print da tela (todos os monitores) pro Ultron ver. Uso: python atalhos/tela.py

Salva em .estado/telas/ e imprime o caminho (o Claude abre a imagem com o Read). Guarda só os 5 últimos.
Windows: roda o tela.ps1 (sem instalar nada). Mac: screencapture.
"""
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PASTA = AQUI.parent / ".estado" / "telas"
GUARDAR = 5


def comando_do_print(destino):
    """O comando que salva o print em destino, no sistema atual."""
    if sys.platform == "darwin":
        return ["screencapture", "-x", str(destino)]
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(AQUI / "tela.ps1"), str(destino)]


def apagar_antigos():
    """Deixa só os últimos GUARDAR prints na pasta."""
    for velho in sorted(PASTA.glob("tela-*.png"))[:-GUARDAR]:
        velho.unlink(missing_ok=True)


def main():
    PASTA.mkdir(parents=True, exist_ok=True)
    destino = PASTA / f"tela-{time.strftime('%H%M%S')}.png"
    r = subprocess.run(comando_do_print(destino), capture_output=True, text=True, timeout=30)
    if not destino.exists():
        sys.exit("Não consegui tirar o print: " + (r.stderr or r.stdout).strip()[-300:])
    apagar_antigos()
    print(destino)


if __name__ == "__main__":
    main()
