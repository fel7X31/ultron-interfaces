"""Copiados (a seção da barra): os últimos textos copiados, pra copiar de novo."""
from ...recursos import copiados
from ..servidor import rota


@rota("GET", "/api/copiados")
def ver(pedido):
    return copiados.listar()


@rota("POST", "/api/copiados/copiar")
def copiar(pedido):
    copiados.copiar(str(pedido.json().get("id", "")))
    return {"ok": True}


@rota("POST", "/api/copiados/apagar")
def apagar(pedido):
    copiados.apagar(str(pedido.json().get("id", "")))
    return {"ok": True}
