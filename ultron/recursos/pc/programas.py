"""Abrir e fechar programas pelo nome falado (spotify, chrome, calculadora, rocket league...)."""
import os
import shutil
import subprocess

from ...nucleo.texto import normalizar
from . import apps, janelas

SOLTO = getattr(subprocess, "DETACHED_PROCESS", 0)

# Nome falado (sem acento) -> como o Windows abre (programas fora do PATH, apps da loja, links de app)
COMO_ABRIR = {
    "spotify": "spotify:", "whatsapp": "whatsapp:", "configuracoes": "ms-settings:", "calculadora": "calc",
    "bloco de notas": "notepad", "explorador": "explorer", "arquivos": "explorer", "vscode": "code",
    "vs code": "code", "navegador": "https://www.google.com", "chrome": "chrome", "edge": "msedge",
    "discord": "discord:", "steam": "steam:", "teams": "msteams:", "gerenciador de tarefas": "taskmgr",
    "terminal": "wt", "paint": "mspaint", "camera": "microsoft.windows.camera:", "loja": "ms-windows-store:",
}
NAVEGADORES = ("chrome", "msedge", "firefox", "samsunginternet", "opera", "brave")
# Nome falado -> nomes dos .exe, pra achar as janelas na hora de fechar. Sem entrada aqui, vale o próprio nome ou
# um pedaço do título ("calculadora" acha a janela "Calculadora").
PROCESSOS = {
    "vscode": ("code",), "vs code": ("code",), "bloco de notas": ("notepad",), "explorador": ("explorer",),
    "arquivos": ("explorer",), "navegador": NAVEGADORES, "edge": ("msedge",), "word": ("winword",),
    "powerpoint": ("powerpnt",), "terminal": ("windowsterminal",), "paint": ("mspaint",),
    "gerenciador de tarefas": ("taskmgr",),
}


def conhecido(nome):
    """O nome falado é de um programa da lista ou instalado no PC? (os comandos de voz abrem e fecham esses na hora)"""
    chave = " ".join(normalizar(nome))
    return chave in COMO_ABRIR or chave in PROCESSOS or apps.achar(nome, apps.guardado()) is not None


def abrir(nome):
    """Abre site, arquivo, pasta ou programa e devolve o nome do que abriu.

    Programa vai pelo nome mais parecido entre os instalados (apps.py): "abre o rocket league" acha o jogo, sem
    precisar do nome do .exe. Sem achar, ValueError com a explicação (nada de janela de erro do Windows).
    """
    alvo = nome.strip().strip('"')
    alvo = COMO_ABRIR.get(" ".join(normalizar(alvo)), alvo)
    if not alvo:
        raise ValueError("Falta dizer o que abrir.")
    if os.path.exists(alvo) or "://" in alvo or alvo.endswith(":"):
        os.startfile(alvo)
        return alvo
    if shutil.which(alvo):
        subprocess.Popen([shutil.which(alvo)], creationflags=SOLTO)
        return alvo
    app = apps.achar(alvo) or apps.achar(alvo, apps.catalogo(de_novo=True))  # instalou agora? procura de novo
    if not app:
        raise ValueError(f"Não achei nenhum programa chamado {nome} no PC.")
    apps.abrir(app)
    return app["nome"]


def fechar(nome):
    """Fecha as janelas do programa, como clicar no X. Devolve quantas (ValueError se não achou nenhuma)."""
    fechadas = 0
    for programa in PROCESSOS.get(" ".join(normalizar(nome)), (nome,)):
        try:
            fechadas += janelas.fechar(programa)
        except ValueError:
            pass
    if not fechadas:
        raise ValueError(f"Não achei {nome} aberto.")
    return fechadas
