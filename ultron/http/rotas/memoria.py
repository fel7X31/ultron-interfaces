"""A memória do Ultron (a seção Memória da barra): lembranças e o grafo delas."""
from ...recursos import memoria
from ..servidor import rota


@rota("GET", "/api/memoria")
def ver(pedido):
    lembrancas = memoria.ler()
    return {"lembrancas": lembrancas, "grafo": memoria.grafo(), "total": len(lembrancas),
            "arquivo": str(memoria.arquivo())}


@rota("POST", "/api/memoria")
def guardar(pedido):
    d = pedido.json()
    return memoria.guardar(str(d.get("texto", "")), str(d.get("assunto", "")))


@rota("POST", "/api/memoria/apagar")
def apagar(pedido):
    memoria.apagar(str(pedido.json().get("id", "")))
    return {"ok": True}
