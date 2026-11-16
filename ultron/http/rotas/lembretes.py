"""Lembretes e timers (as seções Lembretes e Timers da barra)."""
from ...recursos import lembretes
from ..servidor import rota


@rota("GET", "/api/lembretes")
def ver(pedido):
    return lembretes.listar()


@rota("POST", "/api/lembretes")
def criar(pedido):
    d = pedido.json()
    return lembretes.criar_lembrete(str(d.get("texto", "")), str(d.get("quando", "")))


@rota("POST", "/api/lembretes/apagar")
def apagar(pedido):
    lembretes.apagar_lembrete(str(pedido.json().get("id", "")))
    return {"ok": True}


@rota("POST", "/api/lembretes/limpar")
def limpar(pedido):
    return {"tirados": lembretes.limpar_avisados()}


@rota("POST", "/api/timers")
def criar_timer(pedido):
    d = pedido.json()
    try:
        segundos = int(float(d.get("segundos", 0)))
    except (TypeError, ValueError):
        raise ValueError("Quantos segundos?") from None
    return lembretes.criar_timer(segundos, str(d.get("nome", "")))


@rota("POST", "/api/timers/cancelar")
def cancelar_timer(pedido):
    return {"cancelados": lembretes.cancelar_timer(str(pedido.json().get("id", "")))}
