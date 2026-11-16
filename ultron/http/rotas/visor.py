"""Visor da tela: mostrar uma foto, PDF ou texto, e entregar o arquivo que a tela pediu."""
from ...recursos import visor
from ..servidor import Resposta, rota


@rota("POST", "/api/mostrar")
def mostrar(pedido):
    return {"item": visor.mostrar(str(pedido.json().get("origem", "")))}


@rota("GET", "/api/arquivo/{id_arquivo}")
def arquivo(pedido, id_arquivo):
    achado = visor.ler(id_arquivo)
    if not achado:
        return 404, {"erro": "Arquivo não encontrado."}
    corpo, tipo = achado
    return Resposta(corpo, tipo)
