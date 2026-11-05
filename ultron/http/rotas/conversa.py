"""Falar com o Ultron: áudio (segurou o espaço), texto (digitou) e interromper."""
import threading

from ...assistente import turno
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
