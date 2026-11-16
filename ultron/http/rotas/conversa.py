"""Falar com o Ultron: áudio (segurou o espaço), texto (digitou), interromper e chamar."""
import threading

from ...assistente import turno
from ...nucleo.log import log
from ..servidor import rota


def _em_segundo_plano(**kwargs):
    threading.Thread(target=turno.processar, kwargs=kwargs, daemon=True).start()


@rota("POST", "/api/audio")
def audio(pedido):
    if turno.ocupado():
        return 409, {"ocupado": True}  # a tela avisa e espera
    if len(pedido.corpo) < 2000:  # toque rápido no espaço, sem fala
        return {"ok": False}
    _em_segundo_plano(audio=pedido.corpo, mime=pedido.cabecalho("Content-Type", "audio/webm"))
    return 202, {"ok": True}


@rota("POST", "/api/texto")
def texto(pedido):
    if turno.ocupado():
        return 409, {"ocupado": True}
    _em_segundo_plano(texto=pedido.json().get("texto", ""))
    return 202, {"ok": True}


@rota("POST", "/api/interromper")
def interromper(pedido):
    return {"interrompeu": turno.interromper()}


@rota("POST", "/api/chamar")
def chamar(pedido):
    """O botão do microfone da barra: o palmas.py (que cuida do microfone) começa a ouvir, como ao dizer "Ultron"."""
    if turno.ocupado():
        return 409, {"ocupado": True}
    log({"evento": "chamar"})
    return {"ok": True}
