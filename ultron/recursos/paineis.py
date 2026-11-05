"""O que os painéis da tela mostram (e-mails, agenda, mercado, tarefas). Os recursos preenchem; a tela lê em /api/paineis."""
from ..nucleo.eventos import EVENTOS

PAINEIS = {"emails": None, "nao_lidos": None, "agenda": None, "mercado": None, "tarefas": None,
           "google_quando": None, "google_erro": None}


def avisar_paineis():
    """Diz pra tela buscar os painéis de novo."""
    EVENTOS.emitir({"tipo": "paineis"})
