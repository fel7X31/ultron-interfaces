#!/usr/bin/env python3
"""Pergunta a outra IA (ChatGPT, Gemini ou Grok) e imprime a resposta. Uso:
  python atalhos/perguntar_ia.py gemini "Resuma a teoria da relatividade em duas frases"
A chave de cada uma fica no .env (veja ultron/recursos/ias.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ultron.recursos import ias  # noqa: E402


def main():
    for saida in (sys.stdout, sys.stderr):  # o terminal do Windows quebra os acentos sem isso
        saida.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 3 or sys.argv[1] not in ias.PROVEDORES:
        sys.exit(__doc__ + "IAs: " + ", ".join(ias.PROVEDORES))
    ia, pergunta = sys.argv[1], " ".join(sys.argv[2:])
    try:
        print(ias.perguntar(ia, [{"role": "user", "content": pergunta}]))
    except ValueError as erro:
        sys.exit(f"Não deu: {erro}")
    except OSError as erro:
        sys.exit(f"O {ias.nome(ia)} não respondeu: {erro}")


if __name__ == "__main__":
    main()
