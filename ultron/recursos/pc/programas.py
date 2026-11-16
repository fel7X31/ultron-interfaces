"""Abrir e fechar programas pelo nome falado (spotify, chrome, calculadora...)."""
import os
import shutil
import subprocess
import sys

from ...nucleo.texto import normalizar
from . import janelas

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
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
    """O nome falado é de um programa da lista? (os comandos de voz só abrem e fecham esses, na hora)"""
    chave = " ".join(normalizar(nome))
    return chave in COMO_ABRIR or chave in PROCESSOS


def abrir(nome):
    """Abre site, arquivo, pasta ou programa. Devolve o que mandou abrir."""
    alvo = nome.strip().strip('"')
    alvo = COMO_ABRIR.get(" ".join(normalizar(alvo)), alvo)
    if not alvo:
        raise ValueError("Falta dizer o que abrir.")
    if sys.platform == "darwin":
        subprocess.Popen(["open", alvo] if os.path.exists(alvo) or ":" in alvo else ["open", "-a", alvo])
    elif os.path.exists(alvo) or "://" in alvo or alvo.endswith(":"):
        os.startfile(alvo)
    elif shutil.which(alvo):
        subprocess.Popen([shutil.which(alvo)], creationflags=SOLTO)
    else:  # deixa o Windows achar (apps da loja, atalhos do menu iniciar)
        subprocess.Popen(["cmd", "/c", "start", "", alvo], creationflags=SEM_JANELA)
    return alvo


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
