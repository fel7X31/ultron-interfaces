"""O ícone do Ultron: a imagem que vale agora (a aba e o rosto usam) e trocar ou voltar pro robô."""
from ...nucleo.eventos import EVENTOS
from ...recursos import icone
from ..servidor import Resposta, rota


@rota("GET", "/icone.svg")
def imagem(pedido):
    """O nome é o do arquivo antigo pra aba continuar achando; com imagem sua, vem a imagem (o tipo diz qual)."""
    return Resposta(*icone.imagem())


@rota("GET", "/api/icone")
def ver(pedido):
    return icone.situacao()


@rota("POST", "/api/icone")
def trocar(pedido):
    """O corpo é a própria imagem, com o Content-Type dela."""
    return _avisar(icone.salvar(pedido.corpo, pedido.cabecalho("Content-Type")))


@rota("POST", "/api/icone/apagar")
def apagar(pedido):
    return _avisar(icone.apagar())


def _avisar(situacao):
    EVENTOS.emitir({"tipo": "icone", **situacao})
    return situacao
