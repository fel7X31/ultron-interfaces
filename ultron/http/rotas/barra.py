"""A barra do topo da tela: o que ela precisa saber ao abrir, e o aviso da tela quando é minimizada ou volta."""
from ...assistente import cerebro
from ...nucleo.config import CFG
from ...nucleo.eventos import EVENTOS
from ...recursos import barra
from ..servidor import rota


@rota("GET", "/api/barra")
def ver(pedido):
    return {**barra.situacao(), "tema": CFG["tema"], "estado": EVENTOS.ultimo_estado.get("estado"),
            "ia": cerebro.nome_atual()}


@rota("POST", "/api/barra/tela")
def tela(pedido):
    barra.tela_mudou(bool(pedido.json().get("visivel")))
    return {"ok": True}
