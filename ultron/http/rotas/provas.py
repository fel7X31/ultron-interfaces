"""Modo prova: a lista de questões e marcar certa/errada (com a correção)."""
from ...nucleo.config import CFG
from ...recursos import provas
from ..servidor import rota


@rota("GET", "/api/provas")
def listar(pedido):
    return {"modo_prova": CFG["modo_prova"], "provas": provas.carregar_provas()}


@rota("POST", "/api/provas")
def atualizar(pedido):
    provas.atualizar_prova(pedido.json())
    return {"ok": True}
