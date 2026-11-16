#!/usr/bin/env python3
"""Abre um site, arquivo, pasta ou programa no computador do dono. Uso:
  python atalhos/abrir.py "https://youtube.com"
  python atalhos/abrir.py "C:/Users/Miguel Felix/Downloads"
  python atalhos/abrir.py spotify        (programa pelo nome: spotify, notepad, calc, explorer, code...)
Só abre na tela; não apaga nem muda nada. Os nomes conhecidos ficam em ultron/recursos/pc/programas.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ultron.recursos.pc.programas import abrir  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        print("Aberto:", abrir(" ".join(sys.argv[1:])))
    except ValueError as erro:
        print(erro)


if __name__ == "__main__":
    main()
