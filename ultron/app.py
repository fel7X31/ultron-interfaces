"""Liga o Ultron: confere o ambiente, sobe o servidor web, aquece o Claude e roda as rotinas dos painéis."""
import os
import shutil
import signal
import sys
import threading
import time
import webbrowser

from .assistente.sessao import SESSAO
from .assistente.turno import aquecer
from .http.servidor import criar_servidor
from .nucleo.config import CFG
from .recursos.google import atualizar_google
from .recursos.historico import manutencao
from .recursos.mercado import atualizar_mercado
from .recursos.paineis import PAINEIS
from .recursos.tarefas import atualizar_tarefas


def _em_segundo_plano(funcao):
    threading.Thread(target=funcao, daemon=True).start()


def rotinas():
    """Relógio dos painéis. Checa a cada 3 s; cada coisa tem o seu intervalo."""
    proximo_mercado = 0
    proximo_google = time.time() + 12      # deixa o Ultron aquecer primeiro
    proxima_manutencao = time.time() + 20
    while True:
        agora = time.time()
        atualizar_tarefas()                # só lê o tarefas.md: barato
        if agora >= proxima_manutencao:
            proxima_manutencao = agora + 3600
            _em_segundo_plano(manutencao)
        if agora >= proximo_mercado:
            proximo_mercado = agora + 300
            _em_segundo_plano(atualizar_mercado)
        # Google veio vazio ou falhou sem nada na tela: tenta de novo em 45 s em vez de esperar o intervalo todo
        if PAINEIS.pop("tentar_logo", False) or (PAINEIS.get("google_erro") and not PAINEIS.get("emails")
                                                 and proximo_google - agora > 60):
            proximo_google = agora + 45
        if CFG["paineis_min"] > 0 and agora >= proximo_google:
            proximo_google = agora + CFG["paineis_min"] * 60
            _em_segundo_plano(atualizar_google)
        time.sleep(3)


def completar_path():
    """Quando abre pelo app (fora do terminal), o PATH vem curto. Procura nos lugares de costume."""
    atual = os.environ.get("PATH", "").split(os.pathsep)
    for pasta in ("~/.npm-global/bin", "~/.local/bin", "~/.claude/local", "/opt/homebrew/bin",
                  "/usr/local/bin", "/opt/homebrew/opt/ffmpeg-full/bin"):
        pasta = os.path.expanduser(pasta)
        if os.path.isdir(pasta) and pasta not in atual:
            atual.append(pasta)
    os.environ["PATH"] = os.pathsep.join(atual)


def conferir_ambiente():
    completar_path()
    if not CFG["pasta"].is_dir():
        sys.exit(f"ULTRON_PASTA não existe: {CFG['pasta']}")
    if not shutil.which("claude"):
        sys.exit("Não achei o Claude Code (comando 'claude'). Instale antes: https://claude.com/claude-code")
    if not CFG["eleven_key"]:
        print("Aviso: sem ELEVENLABS_API_KEY. Ele vai responder só em texto na tela.")


def main():
    conferir_ambiente()
    servidor = criar_servidor(CFG["porta"])
    url = f"http://localhost:{CFG['porta']}"
    print(f"Ultron no ar em {url}  (pasta: {CFG['pasta']})")

    def encerrar(*_):
        SESSAO.parar()
        os._exit(0)

    signal.signal(signal.SIGTERM, encerrar)
    _em_segundo_plano(aquecer)
    _em_segundo_plano(rotinas)
    if "--sem-abrir" not in sys.argv:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        SESSAO.parar()
