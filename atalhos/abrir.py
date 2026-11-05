#!/usr/bin/env python3
"""Abre um site, arquivo, pasta ou programa no computador do dono. Uso:
  python atalhos/abrir.py "https://youtube.com"
  python atalhos/abrir.py "C:/Users/Miguel Felix/Downloads"
  python atalhos/abrir.py spotify        (programa pelo nome: spotify, notepad, calc, explorer, code...)
Só abre na tela; não apaga nem muda nada.
"""
import os
import shutil
import subprocess
import sys

# Programas que não estão no PATH: nome falado -> como o Windows abre
CONHECIDOS = {
    "spotify": "spotify:", "whatsapp": "whatsapp:", "configuracoes": "ms-settings:", "configurações": "ms-settings:",
    "calculadora": "calc", "bloco de notas": "notepad", "explorador": "explorer", "arquivos": "explorer",
    "vscode": "code", "vs code": "code", "navegador": "https://www.google.com", "chrome": "chrome", "edge": "msedge",
    "discord": "discord:", "steam": "steam:", "teams": "msteams:",
}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    alvo = " ".join(sys.argv[1:]).strip().strip('"')
    alvo = CONHECIDOS.get(alvo.lower(), alvo)
    if sys.platform == "darwin":
        subprocess.Popen(["open", alvo] if os.path.exists(alvo) or ":" in alvo else ["open", "-a", alvo])
    elif os.path.exists(alvo) or "://" in alvo or alvo.endswith(":"):
        os.startfile(alvo)
    elif shutil.which(alvo):
        subprocess.Popen([shutil.which(alvo)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    else:  # deixa o Windows achar (apps da loja, atalhos do menu iniciar)
        subprocess.Popen(["cmd", "/c", "start", "", alvo], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print("Aberto:", alvo)


if __name__ == "__main__":
    main()
