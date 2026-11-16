"""O que está tocando no Windows (Spotify, YouTube no navegador...) e os botões de tocar, pausar e pular.

Um PowerShell só (o midia.ps1, ligado na primeira consulta) fica vigiando e avisa quando a música muda: o Ultron
guarda a última e manda o evento "tocando" pra tela e pra barra do topo.
"""
import ctypes
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from ...nucleo.config import ESTADO
from ...nucleo.eventos import EVENTOS
from . import janelas, teclado

SCRIPT = Path(__file__).with_name("midia.ps1")
CAPA = ESTADO / "capa"  # a capa do que está tocando (o midia.ps1 salva; a barra mostra por /api/pc/capa)
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BOTOES = {"tocar_pausar": 0xB3, "proxima": 0xB0, "anterior": 0xB1}  # as teclas de mídia do teclado
ATALHO_DO_SITE = {"proxima": (0x10, ord("N")), "anterior": (0xA6,)}  # Shift+N: próximo vídeo do YouTube; Voltar
_VIGIA = {"processo": None, "tocando": {}, "leu": threading.Event()}
_LIGANDO = threading.Lock()


def apertar(botao):
    """Aperta o botão de mídia no que está tocando (Spotify, YouTube no navegador...).

    Vai pelo vigia, direto na sessão de mídia do Windows (como os botões do volume do Windows): a tecla de mídia nem
    sempre chega no app certo. Vídeo do YouTube fora de playlist não deixa o Windows pular: aí usa o atalho do próprio
    site, na janela do vídeo. Sem o vigia, aperta a tecla de mídia do teclado.
    """
    if botao not in BOTOES:
        raise ValueError(f"Botão de mídia desconhecido: {botao}.")
    agora = tocando()
    if botao in ATALHO_DO_SITE and agora.get(botao) is False:
        return _pular_na_janela(botao, agora.get("titulo") or "")
    try:
        _VIGIA["processo"].stdin.write(botao + "\n")
        _VIGIA["processo"].stdin.flush()
    except (AttributeError, OSError, ValueError):
        teclado.apertar(BOTOES[botao], estendida=True)


def _pular_na_janela(botao, titulo):
    """Traz a janela do vídeo pra frente, aperta o atalho do site e devolve a frente pra janela de antes."""
    janela = next((j for j in janelas.listar() if titulo and titulo[:40].lower() in j.titulo.lower()), None)
    if not janela:
        raise ValueError("Esse vídeo não deixa pular por fora, e não achei a janela dele. Deixe a aba dele na frente.")
    antes = ctypes.windll.user32.GetForegroundWindow()
    janelas.trazer_pra_frente(janela.numero)
    time.sleep(0.15)  # a janela ganhar o teclado antes do atalho
    teclado.apertar(*ATALHO_DO_SITE[botao], estendida=botao == "anterior")
    time.sleep(0.1)
    if antes and antes != janela.numero:
        janelas.trazer_pra_frente(antes)


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
        processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.PIPE,
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
