#!/usr/bin/env python3
"""Controla o PC (Windows) e imprime a frase do que fez. Uso: python atalhos/pc.py <ação> [alvo]

  volume 30 | mais_volume [10] | menos_volume [10] | mudo | som
  tocar_pausar | proxima | anterior | tocando          (vale pro que estiver tocando: Spotify, YouTube...)
  abrir spotify | fechar discord | focar chrome | minimizar chrome | maximizar chrome | janelas | area_de_trabalho
  bloquear | brilho 70 | mais_brilho | menos_brilho | configuracoes bluetooth | recortar | uso
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ultron.recursos import pc  # noqa: E402


def main():
    for saida in (sys.stdout, sys.stderr):  # o terminal do Windows quebra os acentos sem isso
        saida.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        print(pc.executar(sys.argv[1], " ".join(sys.argv[2:])))
    except ValueError as erro:
        sys.exit(f"Não deu: {erro}")


if __name__ == "__main__":
    main()
