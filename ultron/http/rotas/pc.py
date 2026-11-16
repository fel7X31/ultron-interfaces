"""Controle do PC: o painel da barra (uso, volume, o que está tocando) e as ações (volume, mídia, atalhos...)."""
from ...recursos import pc
from ...recursos.pc import midia
from ..servidor import Resposta, rota


@rota("GET", "/api/pc")
def estado(pedido):
    return pc.estado()


@rota("POST", "/api/pc/acao")
def acao(pedido):
    d = pedido.json()
    return {"texto": pc.executar(str(d.get("acao", "")), str(d.get("alvo", "")))}


@rota("GET", "/api/pc/tocando")
def tocando(pedido):
    """O que está tocando (a barra mostra no entalhe). As mudanças chegam depois pelo evento "tocando"."""
    return {"tocando": midia.tocando()}


@rota("GET", "/api/pc/capa")
def capa(pedido):
    """A capa da música (ou do vídeo) que está tocando, pro entalhe e pro player da barra."""
    achou = midia.capa()
    if not achou:
        return 404, {}
    return Resposta(*achou, cabecalhos={"Cache-Control": "no-store"})
