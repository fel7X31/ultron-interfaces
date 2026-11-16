"""Coisas do Windows: bloquear o PC, brilho da tela, recorte de tela e páginas das Configurações."""
import ctypes
import os
import subprocess
from pathlib import Path

from ...nucleo.texto import normalizar

SCRIPT_BRILHO = Path(__file__).with_name("brilho.ps1")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PAGINAS = {  # nome falado (sem acento) -> página das Configurações
    "bluetooth": "ms-settings:bluetooth", "wifi": "ms-settings:network-wifi", "wi fi": "ms-settings:network-wifi",
    "rede": "ms-settings:network", "internet": "ms-settings:network", "som": "ms-settings:sound",
    "audio": "ms-settings:sound", "tela": "ms-settings:display", "monitor": "ms-settings:display",
    "energia": "ms-settings:powersleep", "bateria": "ms-settings:batterysaver",
    "atualizacoes": "ms-settings:windowsupdate", "windows update": "ms-settings:windowsupdate",
    "aplicativos": "ms-settings:appsfeatures", "apps": "ms-settings:appsfeatures",
    "notificacoes": "ms-settings:notifications", "papel de parede": "ms-settings:personalization-background",
    "cores": "ms-settings:colors", "tema": "ms-settings:themes", "mouse": "ms-settings:mousetouchpad",
    "teclado": "ms-settings:typing", "impressora": "ms-settings:printers", "armazenamento": "ms-settings:storagesense",
    "privacidade": "ms-settings:privacy", "data e hora": "ms-settings:dateandtime", "idioma": "ms-settings:regionlanguage",
}


def bloquear():
    ctypes.windll.user32.LockWorkStation()


def recortar_tela():
    """Abre o recorte de tela do Windows (o mesmo do Win+Shift+S)."""
    os.startfile("ms-screenclip:")


def configuracoes(pagina=""):
    """Abre as Configurações do Windows, na página pedida se ela for conhecida. Devolve a página ("" = início)."""
    chave = " ".join(normalizar(pagina))
    os.startfile(PAGINAS.get(chave, "ms-settings:"))
    return chave if chave in PAGINAS else ""


def brilho(nivel=None):
    """Muda o brilho da tela do notebook (0 a 100), ou só lê sem nível. Devolve o brilho atual."""
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT_BRILHO)]
    if nivel is not None:
        cmd.append(str(max(0, min(100, int(nivel)))))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=SEM_JANELA)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError("Essa tela não deixa mudar o brilho por aqui (só a do notebook deixa).") from None
