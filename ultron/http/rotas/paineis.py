"""Painéis da tela: e-mails, agenda (o + de compromisso), mercado e tarefas."""
from ...nucleo.log import log_erro
from ...recursos import google, tarefas
from ...recursos.paineis import PAINEIS
from ..servidor import rota


@rota("GET", "/api/paineis")
def paineis(pedido):
    return PAINEIS


@rota("GET", "/api/email/{id_email}")
def email(pedido, id_email):
    try:
        return google.ler_email(google.limpar_id(id_email))
    except Exception as erro:
        log_erro("email_falhou", erro)
        return 502, {"erro": "Não consegui abrir esse e-mail."}


@rota("POST", "/api/evento")
def compromisso(pedido):
    """O + da Agenda: aparece no calendário na hora; o Google é atualizado em segundo plano."""
    try:
        google.salvar_compromisso(pedido.json())
    except ValueError as erro:
        return 400, {"ok": False, "erro": str(erro)}
    return {"ok": True}


@rota("POST", "/api/tarefa")
def tarefa(pedido):
    """+, marcar feita, editar, apagar e dificuldade no painel de Tarefas."""
    tarefas.mexer_tarefas(pedido.json())
    return {"ok": True}
