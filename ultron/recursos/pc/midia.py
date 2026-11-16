"""O que está tocando no Windows (Spotify, YouTube no navegador...) e os botões de tocar, pausar e pular.

Um PowerShell só (o midia.ps1, ligado na primeira consulta) fica vigiando e avisa quando a música muda: o Ultron
guarda a última e manda o evento "tocando" pra tela e pra barra do topo.
"""
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from ...nucleo.config import ESTADO
from ...nucleo.eventos import EVENTOS
from . import teclado

SCRIPT = Path(__file__).with_name("midia.ps1")
CAPA = ESTADO / "capa"  # a capa do que está tocando (o midia.ps1 salva; a barra mostra por /api/pc/capa)
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BOTOES = {"tocar_pausar": 0xB3, "proxima": 0xB0, "anterior": 0xB1}  # as teclas de mídia do teclado
_VIGIA = {"processo": None, "tocando": {}, "leu": threading.Event()}
_LIGANDO = threading.Lock()


def apertar(botao):
    """Aperta o botão de mídia (vale pro que estiver tocando: Spotify, YouTube, o player do Ultron...)."""
    if botao not in BOTOES:
        raise ValueError(f"Botão de mídia desconhecido: {botao}.")
    teclado.apertar(BOTOES[botao], estendida=True)


def tocando():
    """{"titulo", "artista", "app", "tocando"} do que está tocando agora, ou {} (liga o vigia na primeira vez)."""
    if _ligar_vigia():
        _VIGIA["leu"].wait(4)  # acabou de ligar: espera a primeira leitura
    return _VIGIA["tocando"]


def capa():
    """(bytes, tipo) da capa do que está tocando, ou None."""
    try:
        dados = CAPA.read_bytes()
    except OSError:
        return None
    return dados, "image/png" if dados[1:4] == b"PNG" else "image/jpeg"


def nome_do_app(app):
    """'Spotify.exe' ou 'Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic' -> 'Spotify', 'ZuneMusic'."""
    nome = re.split(r"[!\\/]", app or "")[-1]
    nome = re.sub(r"\.exe$", "", nome, flags=re.I).split(".")[-1]
    return {"chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "internet": "Samsung Internet"}.get(nome.lower(), nome)


def _ligar_vigia():
    """Liga o vigia, se ele não estiver rodando. Devolve se acabou de ligar."""
    with _LIGANDO:
        processo = _VIGIA["processo"]
        if processo and processo.poll() is None:
            return False
        _VIGIA["leu"].clear()
        ESTADO.mkdir(exist_ok=True)
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
               "-Vigiar", "-Dono", str(os.getpid()), "-Capa", str(CAPA)]
        processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    text=True, encoding="utf-8", creationflags=SEM_JANELA)
        _VIGIA["processo"] = processo
        threading.Thread(target=_ouvir, args=(processo,), daemon=True).start()
        return True


def _ouvir(processo):
    """Cada linha do vigia é o que está tocando agora: guarda e avisa a tela e a barra."""
    for linha in processo.stdout:
        try:
            dados = json.loads(linha)
        except ValueError:
            continue
        if dados:
            dados["app"] = nome_do_app(dados.get("app"))
        _VIGIA["tocando"] = dados
        _VIGIA["leu"].set()
        EVENTOS.emitir({"tipo": "tocando", "tocando": dados})
