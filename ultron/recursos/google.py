"""Gmail e Google Agenda pelos conectores do claude.ai (o Claude só com ferramentas de leitura/escrita da agenda).

- atualizar_google(): busca e-mails e eventos pro painel
- ler_email(id): abre um e-mail (com cache)
- salvar_compromisso(dados): o + da Agenda; aparece na hora e salva no Google em segundo plano
"""
import json
import re
import threading
import time

from ..nucleo.claude_cli import claude_json
from ..nucleo.config import CFG
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log, log_erro
from .paineis import PAINEIS, avisar_paineis

PEDIDO_PAINEL = (
    'Busque (1) os 15 e-mails mais recentes da caixa de entrada do Gmail, lidos e não lidos, e (2) os eventos da '
    'agenda principal do Google Agenda do primeiro dia do mês atual até o último dia do mês que vem '
    '(fuso America/Sao_Paulo). Responda SOMENTE com '
    'um JSON válido, sem texto antes ou depois, sem markdown, no formato: {"emails":[{"id":"id da conversa (thread) '
    'no Gmail","de":"nome do remetente","assunto":"...","trecho":"começo do texto do e-mail, até 140 caracteres",'
    '"nao_lido":true_ou_false,'
    '"quando":"HH:MM ou dd/mm"}],"nao_lidos":numero_total_aproximado,"agenda":[{"id":"id do evento",'
    '"titulo":"...","quando":"hoje 14:00, amanhã 09:30 ou sex 18/12 (dia todo)","inicio":"AAAA-MM-DDTHH:MM",'
    '"fim":"AAAA-MM-DDTHH:MM","dia_todo":true_ou_false,"local":"..."}]}. Agenda em ordem de data. '
    'Listas vazias se não houver nada.'
)
LEITURA = "mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Google_Calendar__list_events,mcp__claude_ai_Google_Calendar__list_calendars"
AGENDA = "mcp__claude_ai_Google_Calendar__"
EMAILS_LIDOS = {}  # id -> e-mail completo (não busca de novo)


def limpar_id(texto, permitido=r"A-Za-z0-9_-", tamanho=64):
    return re.sub(rf"[^{permitido}]", "", str(texto or ""))[:tamanho]


# ---------------------------------------------------------------- painel
def atualizar_google():
    inicio = time.time()
    try:
        dados = claude_json(PEDIDO_PAINEL, LEITURA, limite=150)
        if not dados.get("emails") and PAINEIS.get("emails"):  # veio vazio (conector não respondeu): mantém o que tinha
            raise ValueError("consulta do Google voltou sem e-mails")
        PAINEIS.update(emails=dados.get("emails") or [], nao_lidos=dados.get("nao_lidos"),
                       agenda=(dados.get("agenda") or []) + [e for e in (PAINEIS.get("agenda") or []) if e.get("salvando")],
                       google_erro=None)
        threading.Thread(target=pre_ler_emails, daemon=True).start()
        log({"evento": "paineis_google", "segundos": round(time.time() - inicio, 1), "emails": len(PAINEIS["emails"])})
        if not PAINEIS["emails"]:
            PAINEIS["tentar_logo"] = True  # veio vazio: tenta de novo daqui a pouco
    except Exception as erro:
        PAINEIS["google_erro"] = "Não consegui ler o Google agora."
        log_erro("paineis_falhou", erro)
    PAINEIS["google_quando"] = time.strftime("%H:%M")
    avisar_paineis()


# ---------------------------------------------------------------- e-mail
def ler_email(id_email):
    if id_email in EMAILS_LIDOS:
        return EMAILS_LIDOS[id_email]
    pedido = ("Abra a conversa do Gmail com id " + id_email + " (ferramenta get_thread) e responda SOMENTE com um JSON "
              'válido, sem markdown: {"de":"nome <email>","assunto":"...","data":"dd/mm/aaaa HH:MM",'
              '"texto":"o corpo da mensagem mais recente em texto simples, sem HTML, até 6000 caracteres"}. '
              "Não marque como lido, não responda, não mude nada.")
    EMAILS_LIDOS[id_email] = claude_json(pedido, "mcp__claude_ai_Gmail__get_thread")
    return EMAILS_LIDOS[id_email]


def pre_ler_emails():
    """Deixa os 5 primeiros já abertos: clicar no painel abre na hora."""
    for m in (PAINEIS.get("emails") or [])[:5]:
        id_email = limpar_id(m.get("id"))
        if id_email and id_email not in EMAILS_LIDOS:
            try:
                ler_email(id_email)
            except Exception as erro:
                log_erro("email_falhou", erro, onde="pre-leitura")


# ---------------------------------------------------------------- agenda
def validar_compromisso(d):
    """Dados da tela -> evento limpo. Levanta ValueError com a mensagem pra mostrar."""
    id_ev = limpar_id(d.get("id"), r"A-Za-z0-9_@.-", 128)
    if d.get("excluir") and id_ev:
        return {"id": id_ev, "excluir": True}
    try:
        ev = {"titulo": str(d.get("titulo", ""))[:120], "data": str(d.get("data", ""))[:10],
              "hora": str(d.get("hora", ""))[:5], "duracao_minutos": int(d.get("duracao", 60)),
              "dia_todo": bool(d.get("dia_todo")), "local": str(d.get("local", ""))[:120]}
    except (TypeError, ValueError):
        raise ValueError("Dados do compromisso inválidos.")
    if id_ev:
        ev["id"] = id_ev
    if ev["dia_todo"]:
        ev.pop("hora"), ev.pop("duracao_minutos")
    if not ev["titulo"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ev["data"]) or (
            not ev["dia_todo"] and not re.fullmatch(r"\d{2}:\d{2}", ev.get("hora", ""))):
        raise ValueError("Preencha título, data e hora.")
    return ev


def evento_provisorio(ev):
    """Como o evento aparece no calendário enquanto é salvo no Google."""
    if ev.get("dia_todo"):
        ini, fim, quando = ev["data"], ev["data"], "dia todo"
    else:
        h, m = map(int, ev["hora"].split(":"))
        total = h * 60 + m + int(ev.get("duracao_minutos", 60))
        fim_h, fim_m = min(23, total // 60), total % 60 if total // 60 < 24 else 59
        ini, fim, quando = f"{ev['data']}T{ev['hora']}", f"{ev['data']}T{fim_h:02d}:{fim_m:02d}", ev["hora"]
    return {"id": ev.get("id", ""), "titulo": ev["titulo"], "inicio": ini, "fim": fim, "dia_todo": bool(ev.get("dia_todo")),
            "local": ev.get("local", ""), "quando": quando, "salvando": True}


def salvar_compromisso(dados):
    """Criar, editar ou excluir. Muda o painel na hora e manda pro Google em segundo plano."""
    ev = validar_compromisso(dados)
    agenda = PAINEIS.get("agenda") or []
    PAINEIS["agenda"] = agenda
    provisorio = None
    if ev.get("excluir"):
        PAINEIS["agenda"] = [e for e in agenda if e.get("id") != ev["id"]]
    else:
        provisorio = evento_provisorio(ev)
        i = next((i for i, e in enumerate(agenda) if ev.get("id") and e.get("id") == ev["id"]), None)
        if i is not None:
            agenda[i] = provisorio
        elif not ev.get("id"):
            agenda.append(provisorio)
    avisar_paineis()
    threading.Thread(target=_salvar_no_google, args=(ev, provisorio), daemon=True).start()


def _salvar_no_google(ev, provisorio):
    try:
        r = _pedir_ao_google(ev)
    except Exception as erro:
        r = {"ok": False, "erro": repr(erro)[:200]}
    log({"evento": "evento_criado" if r.get("ok") else "evento_falhou", "detalhe": json.dumps(r, ensure_ascii=False)[:300]})
    if provisorio is not None:
        provisorio.pop("salvando", None)
    if not r.get("ok"):
        if provisorio is not None and provisorio in (PAINEIS.get("agenda") or []) and not ev.get("id"):
            PAINEIS["agenda"].remove(provisorio)
        EVENTOS.aviso(f"Não consegui salvar o compromisso na agenda, {CFG['nome']}.")
        avisar_paineis()
    atualizar_google()


def _pedir_ao_google(ev):
    fim = ('. Depois responda SOMENTE com um JSON válido: {"ok":true,"titulo":"...","quando":"..."} '
           'ou {"ok":false,"erro":"motivo curto"}.')
    if ev.get("excluir"):
        pedido = "Exclua da agenda principal do Google Agenda o evento com id " + ev["id"] + ". Não mexa em mais nada" + fim
        return claude_json(pedido, AGENDA + "delete_event")
    dados = json.dumps({k: v for k, v in ev.items() if k not in ("id", "excluir")}, ensure_ascii=False)
    if ev.get("id"):
        pedido = ("Atualize o evento com id " + ev["id"] + " na agenda principal do Google Agenda (fuso America/Sao_Paulo) "
                  "pra ficar exatamente com estes dados, sem mexer em convidados: " + dados + fim)
        return claude_json(pedido, AGENDA + "update_event," + AGENDA + "get_event")
    pedido = ("Crie UM evento na agenda principal do Google Agenda (fuso America/Sao_Paulo) com estes dados, "
              "exatamente como estão, sem convidados: " + dados + fim)
    return claude_json(pedido, AGENDA + "create_event," + AGENDA + "list_calendars")
