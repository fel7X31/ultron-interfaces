"""Quem responde: o Claude (e qual modelo) ou outra IA. A tela e a barra mostram as opções e trocam por aqui."""
from ...assistente import cerebro
from ...recursos import contas_ia, ias
from ..servidor import rota


@rota("GET", "/api/ias")
def ver(pedido):
    """Quem responde agora (outra, se a que você escolheu chegou no limite) e as opções."""
    ia, modelo = ias.quem_responde()
    return {"ia": ia, "modelo": modelo, "nome": ias.nome(ia, modelo), "opcoes": ias.opcoes()}


@rota("POST", "/api/ias")
def escolher(pedido):
    d = pedido.json()
    cerebro.escolher(str(d.get("ia", "")), str(d.get("modelo") or ""))
    return ver(pedido)


@rota("POST", "/api/ias/entrar")
def entrar(pedido):
    """Abre o login da IA (Gemini com o Google, ChatGPT com a conta dele) numa janela do terminal."""
    contas_ia.entrar(str(pedido.json().get("ia", "")))
    return {"ok": True}
