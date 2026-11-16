"""Lembretes e timers: o Ultron avisa falando na hora certa.

- Lembretes ("me lembra de ligar pra mãe às 19h") ficam em <sua pasta>/lembretes.md, um por linha:
  "- [ ] 2026-11-15 19:00 · ligar pra mãe" ([x] = já avisou). Dá pra editar à mão, e o Claude também escreve lá.
- Timers ("timer de 5 minutos") ficam só na memória: somem se o Ultron desligar.
O app.py chama conferir() a cada 3 s: o que venceu vira um aviso falado na tela e na barra.
"""
import datetime as dt
import hashlib
import itertools
import re
import threading
import time

from ..nucleo.config import CFG
from ..nucleo.eventos import EVENTOS
from ..voz.fala import url_fala

TRAVA = threading.Lock()
FORMATO = "%Y-%m-%d %H:%M"
LINHA = re.compile(r"^- \[([ xX])\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.+)$")
CABECALHO = "# Lembretes do Ultron\n\nUm por linha: `- [ ] AAAA-MM-DD HH:MM · o que lembrar`. [x] = já avisou.\n"
MAIOR_TIMER_S = 24 * 3600
TIMERS = {}  # id -> {"id", "nome", "fim", "segundos", "rotulo"}
_NUMERO_DO_TIMER = itertools.count(1)

NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
           "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30,
           "quarenta": 40, "cinquenta": 50, "sessenta": 60, "noventa": 90, "meia": 0.5}
UNIDADES = {"h": 3600, "hora": 3600, "horas": 3600, "min": 60, "mins": 60, "minuto": 60, "minutos": 60,
            "s": 1, "seg": 1, "segundo": 1, "segundos": 1}
PERIODOS = {"manha": 0, "tarde": 12, "noite": 12, "madrugada": 0}


# ---------------------------------------------------------------- entender o tempo falado (frase já normalizada)
def duracao(palavras):
    """Segundos de "5 minutos", "uma hora e meia", "meia hora", "1h30", "vinte e cinco min"... ou None."""
    total, numero, ultima_unidade = 0, None, None
    for p in palavras:
        if (m := re.fullmatch(r"(\d+)h(\d{1,2})?", p)):
            total += int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60
            numero, ultima_unidade = None, 3600
        elif (m := re.fullmatch(r"(\d+)(min|s)", p)):
            total += int(m.group(1)) * UNIDADES[m.group(2)]
            numero, ultima_unidade = None, UNIDADES[m.group(2)]
        elif p == "meia" and numero is None and ultima_unidade:  # "uma hora e meia"
            total += ultima_unidade // 2
        elif p.isdigit() or p in NUMEROS:
            numero = (numero or 0) + (int(p) if p.isdigit() else NUMEROS[p])
        elif p in UNIDADES:
            total += (1 if numero is None else numero) * UNIDADES[p]
            numero, ultima_unidade = None, UNIDADES[p]
        elif p != "e":
            numero = None
    if not total and numero:  # "timer de 5": minutos
        total = numero * 60
    return int(total) or None


def _em_digitos(palavras):
    return [str(int(NUMEROS[p])) if p in NUMEROS and p != "meia" else p for p in palavras]


def _hora_do_relogio(frase):
    """(hora, minuto, período) de "as 15h", "as 3 e meia da tarde", "as 9 30", "meio dia"... ou None."""
    if re.search(r"\bmeio dia\b", frase):
        return 12, 0, "tarde"
    if re.search(r"\bmeia noite\b", frase):
        return 0, 0, "madrugada"
    m = re.search(r"\b(?:as|pras|para as|ate as|a(?= 1\b))\s+(\d{1,2})(?:h(\d{2})?|\s+horas?)?"
                  r"(?:\s+(?:e\s+)?(\d{2}|meia|\d{1,2}(?=\s+minutos?))(?:\s+minutos?)?)?"
                  r"(?:\s+(?:da|de)\s+(manha|tarde|noite|madrugada))?", frase)
    if not m:
        return None
    hora = int(m.group(1))
    minuto = 30 if m.group(3) == "meia" else int(m.group(2) or m.group(3) or 0)
    if hora > 23 or minuto > 59:
        return None
    return hora, minuto, m.group(4)


def quando(palavras, agora=None):
    """A data e hora de um lembrete falado ("daqui a 10 minutos", "amanhã às 9", "às 3 da tarde"), ou None."""
    agora = agora or dt.datetime.now()
    palavras = list(palavras)
    frase = " ".join(palavras)
    relativo = re.search(r"\b(?:daqui a|daqui|dentro de|em)\s+(.+)$", frase)
    if relativo and (s := duracao(relativo.group(1).split())) and _comeca_com_numero(relativo.group(1)):
        return agora + dt.timedelta(seconds=s)
    relogio = _hora_do_relogio(" ".join(_em_digitos(palavras)))
    if not relogio:
        return None
    hora, minuto, periodo = relogio
    if periodo and hora < 12:
        hora += PERIODOS[periodo]
    dias = 2 if "depois de amanha" in frase else 1 if "amanha" in frase else 0
    alvo = (agora + dt.timedelta(days=dias)).replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if dias or periodo:
        return alvo if alvo > agora else alvo + dt.timedelta(days=1)
    if alvo > agora:
        return alvo
    if hora < 12 and alvo.replace(hour=hora + 12) > agora:  # "às 3" depois das 3 da manhã: 15h
        return alvo.replace(hour=hora + 12)
    return alvo + dt.timedelta(days=1)


def _comeca_com_numero(trecho):
    primeira = trecho.split()[0]
    return primeira[0].isdigit() or primeira in NUMEROS


def falar_duracao(segundos):
    """3725 -> "1 hora e 2 minutos"."""
    h, resto = divmod(int(segundos), 3600)
    m, s = divmod(resto, 60)
    partes = [f"{h} hora{'s' * (h > 1)}" if h else "", f"{m} minuto{'s' * (m > 1)}" if m else "",
              f"{s} segundo{'s' * (s > 1)}" if s and not h else ""]
    partes = [p for p in partes if p]
    return " e ".join(partes) or "0 segundos"


# ---------------------------------------------------------------- lembretes (no lembretes.md)
def arquivo():
    return CFG["pasta"] / "lembretes.md"


def _id(momento, texto):
    return hashlib.sha1(f"{momento} {texto}".encode()).hexdigest()[:8]


def ler():
    """Os lembretes do arquivo, em ordem de hora: [{id, texto, quando, feito}]."""
    try:
        linhas = arquivo().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    lembretes = []
    for linha in linhas:
        if (m := LINHA.match(linha.strip())):
            lembretes.append({"id": _id(m.group(2), m.group(3)), "texto": m.group(3).strip(), "quando": m.group(2),
                              "feito": m.group(1) != " "})
    return sorted(lembretes, key=lambda x: x["quando"])


def _gravar(lembretes):
    linhas = [f"- [{'x' if x['feito'] else ' '}] {x['quando']} · {x['texto']}"
              for x in sorted(lembretes, key=lambda x: x["quando"])]
    arquivo().parent.mkdir(parents=True, exist_ok=True)
    arquivo().write_text(CABECALHO + "\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    EVENTOS.emitir({"tipo": "lembretes"})


def criar_lembrete(texto, momento):
    """Guarda um lembrete. momento: datetime ou "AAAA-MM-DD HH:MM" (ou com T). ValueError se faltar algo."""
    texto = re.sub(r"\s+", " ", texto or "").strip().rstrip(".")
    if not texto:
        raise ValueError("Lembrar do quê?")
    if isinstance(momento, str):
        try:
            momento = dt.datetime.strptime(momento.replace("T", " ")[:16], FORMATO)
        except ValueError:
            raise ValueError("Hora do lembrete inválida.") from None
    if momento < dt.datetime.now() - dt.timedelta(minutes=1):
        raise ValueError("Essa hora já passou.")
    novo = {"id": _id(f"{momento:{FORMATO}}", texto), "texto": texto, "quando": f"{momento:{FORMATO}}", "feito": False}
    with TRAVA:
        _gravar([x for x in ler() if x["id"] != novo["id"]] + [novo])
    return novo


def apagar_lembrete(id_lembrete):
    with TRAVA:
        lembretes = ler()
        restantes = [x for x in lembretes if x["id"] != id_lembrete]
        if len(restantes) == len(lembretes):
            raise ValueError("Esse lembrete não existe mais.")
        _gravar(restantes)


def limpar_avisados():
    """Tira do arquivo os lembretes que já avisaram. Devolve quantos saíram."""
    with TRAVA:
        lembretes = ler()
        pendentes = [x for x in lembretes if not x["feito"]]
        if len(pendentes) != len(lembretes):
            _gravar(pendentes)
        return len(lembretes) - len(pendentes)


# ---------------------------------------------------------------- timers (só na memória)
def criar_timer(segundos, nome=""):
    segundos = int(segundos or 0)
    if not 1 <= segundos <= MAIOR_TIMER_S:
        raise ValueError("O timer vai de 1 segundo a 24 horas.")
    nome = (nome or "").strip()
    timer = {"id": f"t{next(_NUMERO_DO_TIMER)}", "nome": nome, "fim": time.time() + segundos, "segundos": segundos,
             "rotulo": nome or f"Timer de {falar_duracao(segundos)}"}
    TIMERS[timer["id"]] = timer
    EVENTOS.emitir({"tipo": "lembretes"})
    return timer


def cancelar_timer(id_timer=""):
    """Cancela um timer (ou todos, sem id). Devolve quantos cancelou."""
    ids = [id_timer] if id_timer else list(TIMERS)
    cancelados = sum(1 for i in ids if TIMERS.pop(i, None))
    if cancelados:
        EVENTOS.emitir({"tipo": "lembretes"})
    return cancelados


def listar():
    """O que a barra mostra: os lembretes (pendentes primeiro) e os timers rodando, com quanto falta."""
    agora = time.time()
    timers = [{**t, "falta": max(0, round(t["fim"] - agora))} for t in sorted(TIMERS.values(), key=lambda t: t["fim"])]
    lembretes = ler()
    return {"lembretes": [x for x in lembretes if not x["feito"]] + [x for x in lembretes if x["feito"]][-10:],
            "timers": timers}


# ---------------------------------------------------------------- avisar na hora
def conferir(agora=None):
    """Avisa (fala) os lembretes e timers que venceram. O app.py chama a cada 3 s. Devolve as frases ditas."""
    agora = agora or dt.datetime.now()
    frases = [f"{CFG['nome']}, acabou o timer " + (t["nome"] or f"de {falar_duracao(t['segundos'])}") + "."
              for t in _timers_vencidos(agora.timestamp())]
    frases += [f"{CFG['nome']}, lembrete: {x['texto']}." for x in _lembretes_vencidos(agora)]
    for frase in frases:
        avisar(frase)
    return frases


def _timers_vencidos(agora):
    vencidos = [t for t in list(TIMERS.values()) if t["fim"] <= agora]
    for t in vencidos:
        TIMERS.pop(t["id"], None)
    return vencidos


def _lembretes_vencidos(agora):
    with TRAVA:
        lembretes = ler()
        vencidos = [x for x in lembretes if not x["feito"] and x["quando"] <= f"{agora:{FORMATO}}"]
        if vencidos:
            for x in vencidos:
                x["feito"] = True
            _gravar(lembretes)
    return vencidos


def avisar(frase):
    """O aviso na tela e na barra (com um toque), falado se a voz estiver ligada."""
    EVENTOS.emitir({"tipo": "alarme", "texto": frase})
    EVENTOS.aviso(frase)
    audio = url_fala(frase)
    if audio:
        EVENTOS.emitir({"tipo": "fala", "texto": frase, "audio": audio})
    EVENTOS.emitir({"tipo": "lembretes"})
