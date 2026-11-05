"""O turno inteiro de uma fala: ouvir -> comando rápido ou Claude -> responder (texto na tela + voz).

- processar(audio=..., texto=...): roda um turno (uma thread por fala; um turno de cada vez)
- interromper(): barra de espaço no meio da resposta
- aquecer(): primeira chamada ao abrir (ou depois de reiniciar), deixa o Claude pronto
"""
import random
import re
import shlex
import subprocess
import sys
import threading
import time

from ..nucleo.config import ATALHOS, CFG, ESTADO, RAIZ, voz_ligada
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log
from ..nucleo.texto import limpar_para_fala
from ..recursos.google import atualizar_google
from ..recursos.provas import registrar_prova
from ..voz.fala import AVISOS_PRONTOS, com_nome, gravar_avisos_prontos, url_fala
from ..voz.transcricao import transcrever
from . import comandos
from .confirmacao import autorizou_no_pedido, eh_confirmacao, pediu_confirmacao
from .prebusca import prebusca
from .sessao import SESSAO

TOKEN_CONFIRMADO = ESTADO / "confirmado"      # existe = a trava deixa passar neste pedido
AQUECENDO = threading.Event()


class Estado:
    ocupado = threading.Lock()       # um pedido de cada vez
    aguardando_confirmacao = False   # o Ultron perguntou "Confirma?" na última resposta
    interrompido = False             # você apertou espaço no meio: esse pedido não fala mais nada


def ocupado():
    """Tem pedido em andamento (e não foi interrompido)? A tela espera em vez de mandar outro."""
    return Estado.ocupado.locked() and not Estado.interrompido


def interromper():
    if not Estado.ocupado.locked():
        return False
    Estado.interrompido = True
    SESSAO.interromper()
    log({"evento": "interrompido"})
    return True


def reiniciar():
    """Fecha o Claude e abre de novo (botão reiniciar ou troca de nome)."""
    SESSAO.parar()
    Estado.aguardando_confirmacao = False
    threading.Thread(target=aquecer, daemon=True).start()


# ---------------------------------------------------------------- pedaços do turno

def _abrir_trava(texto, registro):
    """Abre quando ele pediu "Confirma?" e você disse sim, ou quando você já deu a permissão no pedido."""
    sim_ao_pedido = Estado.aguardando_confirmacao and eh_confirmacao(texto)
    if sim_ao_pedido or autorizou_no_pedido(texto):
        ESTADO.mkdir(exist_ok=True)
        TOKEN_CONFIRMADO.write_text(str(time.time()))
        registro["confirmou"] = "resposta" if sim_ao_pedido else "no_pedido"


def responder_fixo(resposta, registro):
    """Resposta pronta, sem passar pelo Claude (comandos de voz)."""
    registro["resposta"] = resposta
    EVENTOS.emitir({"tipo": "resposta", "texto": resposta, "audio": url_fala(resposta), "segundos": 0, "confirmar": False})
    EVENTOS.estado("parado")


def _aviso_rapido(registro, inicio):
    """O "Um instante, Senhor." que sai enquanto ele trabalha. Usa o texto que ele escreveu, ou uma frase pronta."""
    def avisar(frase=None):
        if Estado.interrompido:
            return
        frase = limpar_para_fala(frase or "")[:160]
        pronta = not frase
        if pronta:
            frase = com_nome(random.choice(AVISOS_PRONTOS))
        registro["aviso"] = frase + (" (pronta)" if pronta else "")
        registro["aviso_s"] = round(time.time() - inicio, 2)
        if voz_ligada():
            EVENTOS.emitir({"tipo": "fala", "texto": frase, "audio": url_fala(frase, fixa=pronta)})
    return avisar


def _dividir_para_voz(resposta):
    """A primeira frase sai antes (começa a falar mais cedo); o resto entra na fila logo depois."""
    if voz_ligada():
        partes = re.split(r"(?<=[.!?])\s+", resposta, maxsplit=1)
        if len(partes) == 2 and len(partes[0]) >= 8 and len(partes[1]) >= 8:
            return partes[0], partes[1]
    return resposta, ""


def _perguntar_ao_claude(texto, registro, inicio):
    EVENTOS.estado("pensando")
    t_claude = time.time()
    dados = prebusca(texto)
    if dados:
        registro["prebusca_s"] = round(time.time() - t_claude, 2)
    r = SESSAO.perguntar(texto + dados, ao_avisar=_aviso_rapido(registro, inicio), aviso_apos=2.5 if dados else None)
    registro["claude_s"] = round(time.time() - t_claude, 2)
    registro["cedo"] = bool(r.get("cedo"))
    if SESSAO.turno:
        registro["etapas"] = {k: v for k, v in SESSAO.turno.marcas.items() if k != "envio"}
    return r


def _responder(texto, r, registro, inicio):
    registro["ferramentas"] = SESSAO.ferramentas_turno
    if any("Google_Calendar" in f or "Gmail" in f for f in (SESSAO.ferramentas_turno or [])):
        threading.Thread(target=atualizar_google, daemon=True).start()  # ele mexeu no Google: atualiza o painel
    if CFG["modo_texto"]:
        resposta = (r.get("result") or "").strip()[:4000] or "Feito."
    else:
        resposta = limpar_para_fala(r.get("result") or "") or "Feito."
    if r.get("is_error"):
        registro["erro"] = r.get("result")
    Estado.aguardando_confirmacao = pediu_confirmacao(resposta)
    primeira, resto = _dividir_para_voz(resposta)
    audio = url_fala(primeira)
    audio_resto = url_fala(resto)
    registro["resposta"] = resposta
    registro["total_s"] = round(time.time() - inicio, 2)
    if CFG["modo_prova"] and not r.get("is_error"):
        registrar_prova(texto, resposta)
    EVENTOS.emitir({"tipo": "resposta", "texto": resposta, "audio": audio,
                    "segundos": registro["total_s"], "confirmar": Estado.aguardando_confirmacao})
    if audio_resto:  # entra na fila e toca logo depois da primeira frase
        EVENTOS.emitir({"tipo": "fala", "texto": resto, "audio": audio_resto})
    EVENTOS.estado("parado")


# ---------------------------------------------------------------- o turno
def processar(audio=None, mime="audio/webm", texto=None):
    # Se o pedido anterior foi interrompido, ele libera em instantes: espera um pouco.
    # Ainda aquecendo (logo depois das palmas): espera ele ficar pronto em vez de recusar a fala.
    espera = 60 if AQUECENDO.is_set() else 10 if Estado.interrompido else 0.01
    if not Estado.ocupado.acquire(timeout=espera):
        EVENTOS.aviso(f"Um pedido de cada vez, {CFG['nome']}. Ainda estou no anterior.")
        return
    inicio = time.time()
    registro = {"evento": "turno"}
    try:
        if audio is not None:
            EVENTOS.estado("transcrevendo")
            texto = transcrever(audio, mime)
            registro["transcricao_s"] = round(time.time() - inicio, 2)
            if Estado.interrompido:
                registro["interrompido"] = True
                return
        texto = (texto or "").strip()
        if not texto:
            EVENTOS.aviso("Não consegui ouvir. Segure o espaço e fale de novo.")
            EVENTOS.estado("parado")
            return
        EVENTOS.emitir({"tipo": "voce", "texto": texto})
        registro["voce"] = texto

        fixa = comandos.tentar(comandos.Fala(texto, Estado.aguardando_confirmacao, registro))
        if fixa is not None:
            if fixa:
                responder_fixo(fixa, registro)
            else:
                EVENTOS.estado("parado")
            return

        _abrir_trava(texto, registro)
        r = _perguntar_ao_claude(texto, registro, inicio)
        if Estado.interrompido or r.get("interrompido"):
            registro["interrompido"] = True
            return
        _responder(texto, r, registro, inicio)
    except Exception as erro:
        registro["erro"] = repr(erro)
        EVENTOS.aviso(f"Deu erro: {erro}")
        EVENTOS.estado("parado")
    finally:
        if TOKEN_CONFIRMADO.exists():
            TOKEN_CONFIRMADO.unlink()
        log(registro)
        Estado.interrompido = False
        Estado.ocupado.release()


# ---------------------------------------------------------------- ao abrir
def aquecer_atalhos():
    """Roda atalhos lentos quando abre (ex.: o resumo da isca de ontem), pra resposta sair na hora."""
    for cmd in filter(None, (c.strip() for c in CFG["aquecer_atalhos"].split(";"))):
        partes = shlex.split(cmd)
        try:
            subprocess.run([sys.executable, str(ATALHOS / partes[0])] + partes[1:],
                           cwd=str(RAIZ), capture_output=True, timeout=180)
            log({"evento": "atalho_aquecido", "comando": cmd})
        except Exception as erro:
            log({"evento": "atalho_falhou", "comando": cmd, "erro": repr(erro)})


def aquecer():
    """Primeira chamada ao abrir: conecta as ferramentas e deixa o Claude pronto."""
    threading.Thread(target=aquecer_atalhos, daemon=True).start()
    EVENTOS.estado("aquecendo")
    AQUECENDO.set()
    try:
        SESSAO.iniciar()
        gravar_avisos_prontos()
        if CFG["aquecer"]:
            with Estado.ocupado:
                SESSAO.perguntar("(Mensagem automática de início. Não use ferramentas. Responda só: Pronto.)", limite=120)
    finally:
        AQUECENDO.clear()
        EVENTOS.estado("parado")
