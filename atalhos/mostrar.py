#!/usr/bin/env python3
"""Mostra uma foto, PDF ou texto na tela do Ultron. Uso:
  python atalhos/mostrar.py "C:/Users/Miguel Felix/Downloads/foto.jpg"
  python atalhos/mostrar.py "https://site.com/imagem.jpg"
Só mostra; não apaga nem muda nada. O Ultron precisa estar ligado.
"""
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    origem = " ".join(sys.argv[1:]).strip().strip('"')
    porta = os.environ.get("ULTRON_PORTA", "8790")
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{porta}/api/mostrar", data=json.dumps({"origem": origem}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            print("Mostrando na tela:", json.load(r)["item"]["nome"])
    except urllib.error.HTTPError as erro:
        print("Não deu:", json.load(erro).get("erro", erro.code))
    except OSError:
        print("O Ultron não respondeu. Está ligado?")


main()
