"""Comandos de voz de lembretes e timers: "me lembra de ligar pra mãe às 19h", "me avisa daqui a 10 minutos de tirar
o bolo", "timer de 5 minutos", "quanto falta no timer?", "cancela o timer". A regra fica em recursos/lembretes.py."""
import re

from ..nucleo.texto import falar_quando
from ..recursos import lembretes
from .comandos import comando

TIMER = re.compile(r"\b(timer|temporizador|cronometr\w*|contagem regressiva)\b")
CANCELAR = re.compile(r"\b(cancel\w*|para|pare|parar|desliga\w*|tira\w*|apaga\w*|zera\w*)\b")
FALTA = re.compile(r"\b(quanto|quantos|quantas)\b.*\b(falta|faltam|resta|restam)\b")
PEDE_LEMBRETE = re.compile(r"^(?:(?:ei|o) )?(?:ultron )?(?:por favor )?(?:me (?:lembr[ae]|avis[ae]|alert[ae])|"
                           r"(?:cri[ae]|coloc[ae]|bot[ae]|faz|faca|anot[ae]) (?:um )?lembrete)\b")
LISTAR = re.compile(r"\b(quais|que|mostra|lista)\b.*\blembretes\b")
SEM_HORA = re.compile(r"\bme (?:lembr[ae]|avis[ae]|alert[ae]) (?:de|da|do|pra|para|que)\b|\blembrete\b")

NUMERO_FALADO = r"(?:\d{1,2}|uma|duas|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|meia)"
GATILHO = re.compile(r"^\W*(?:(?:ei|[oô])\s+)?(?:ultron\W+)?(?:por favor\W+)?(?:me\s+(?:lembr[ae]|avis[ae]|alert[ae])"
                     r"|(?:cri[ae]|coloc[ae]|bot[ae]|faz|fa[çc]a|anot[ae])\s+(?:um\s+)?lembrete)\W*", re.I)
TEMPO = [re.compile(p, re.I) for p in (
    r"\b(?:depois de amanh[ãa]|amanh[ãa]|hoje)\b",
    r"\b(?:[àa]s|pras|para as|at[ée] as)\s+" + NUMERO_FALADO + r"(?:[:h]\d{2}|h)?(?:\s*horas?)?"
    r"(?:\s+e\s+(?:meia|\d{1,2})(?:\s*minutos?)?)?(?:\s+(?:da|de)\s+(?:manh[ãa]|tarde|noite|madrugada))?",
    r"\b(?:ao\s+)?meio[\s-]dia\b|\b(?:[àa]\s+)?meia[\s-]noite\b",
    r"\b(?:daqui\s+a|daqui|dentro\s+de|em)\s+(?:\d+|um|uma|meia|dois|duas|tr[eê]s|quatro|cinco|dez|quinze|vinte|trinta)"
    r"[^,.]*?\b(?:minutos?|min|horas?|h|segundos?|seg)\b(?:\s+e\s+(?:meia|\d+\s*(?:minutos?|min|segundos?)))?",
)]
CONECTIVOS = re.compile(r"^(?:\W|\b(?:de|pra|para|que|e)\b)+|[\s.,!?;:]+$", re.I)


def texto_do_lembrete(texto):
    """O que lembrar, sem o pedido e sem a hora: "Me lembra às 19h de ligar pra mãe." -> "ligar pra mãe"."""
    resto = GATILHO.sub("", texto, count=1)
    for regex in TEMPO:
        resto = regex.sub(" ", resto)
    return CONECTIVOS.sub("", re.sub(r"\s+", " ", resto)).strip()


@comando
def timer(fala):
    if not fala.curta(12) or not TIMER.search(fala.frase):
        return None
    if FALTA.search(fala.frase):
        rodando = lembretes.listar()["timers"]
        if not rodando:
            return "Não tem timer rodando."
        return f"Faltam {lembretes.falar_duracao(rodando[0]['falta'])}."
    if CANCELAR.search(fala.frase):
        cancelados = lembretes.cancelar_timer()
        return "Timer cancelado." if cancelados == 1 else f"{cancelados} timers cancelados." if cancelados \
            else "Não tem timer rodando."
    segundos = lembretes.duracao(fala.palavras)
    if not segundos:
        return "De quanto tempo? Diga, por exemplo: timer de 5 minutos."
    novo = lembretes.criar_timer(segundos)
    fala.registro["timer"] = segundos
    return f"{novo['rotulo']} começando."


@comando
def lembrete(fala):
    if LISTAR.search(fala.frase) and fala.curta(8):
        return _falar_lembretes()
    if not fala.curta(30) or not PEDE_LEMBRETE.search(fala.frase):
        return None
    momento = lembretes.quando(fala.palavras)
    if not momento:  # "me lembra o que eu tinha pra hoje" é pergunta: vai pro Claude
        return "Pra quando? Diga, por exemplo: me lembra de beber água às 15h, ou daqui a 20 minutos." \
            if SEM_HORA.search(fala.frase) else None
    texto = texto_do_lembrete(fala.texto)
    if not texto:
        return "Lembrar do quê?"
    novo = lembretes.criar_lembrete(texto, momento)
    fala.registro["lembrete"] = novo["quando"]
    return f"Combinado. {falar_quando(momento).capitalize()} eu te lembro: {texto}."


def _falar_lembretes():
    pendentes = [x for x in lembretes.listar()["lembretes"] if not x["feito"]]
    if not pendentes:
        return "Nenhum lembrete marcado."
    proximos = "; ".join(f"{x['quando'][11:]}, {x['texto']}" for x in pendentes[:3])
    return f"{len(pendentes)} lembrete{'s' * (len(pendentes) > 1)}. " + proximos + "."
