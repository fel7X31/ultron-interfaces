"""A barra do topo da tela (barra.py, na raiz do projeto): aparece quando a tela do Ultron não está à vista.

A tela avisa quando é minimizada ou volta (rota /api/barra/tela). A barra ouve o evento "barra" e aparece ou some.
"""
from ..nucleo.eventos import EVENTOS

TELA = {"visivel": False}  # o último aviso da tela


def mostrar():
    """A barra aparece quando não há tela do Ultron aberta e à vista."""
    return not (EVENTOS.telas() and TELA["visivel"])


def tela_mudou(visivel):
    """A tela foi minimizada (ou ficou escondida atrás de outra janela) ou voltou."""
    TELA["visivel"] = bool(visivel)
    avisar()


def situacao():
    """Se a barra aparece, e quantas telas estão abertas (sem nenhuma, quem fala as respostas é a barra)."""
    return {"mostrar": mostrar(), "telas": EVENTOS.telas()}


def avisar():
    EVENTOS.emitir({"tipo": "barra", **situacao()})
