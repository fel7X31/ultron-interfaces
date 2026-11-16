"""Quando cada IA chegou no limite de uso do plano e quando ela libera de novo.

Fica em .estado/limites.json ({"claude": 1763226000.0, "chatgpt": ...}, em hora Unix), pra lembrar mesmo depois de
reiniciar. "claude" vale pra todos os modelos do Claude (o limite de 5 horas e o da semana); "claude:opus" e
"claude:sonnet" são o limite da semana de um modelo só. Quem decide pra quem passar é ias.quem_responde().
"""
import datetime as dt
import time

from ..nucleo.arquivos import ler_json, salvar_json
from ..nucleo.config import ESTADO
from ..nucleo.texto import falar_quando

ARQUIVO = ESTADO / "limites.json"
SEM_HORA_S = 3600  # a IA não disse quando libera: tenta de novo daqui a 1 hora
SO_DO_MODELO = {"seven_day_opus": "opus", "seven_day_sonnet": "sonnet"}  # limites do Claude que valem pra um modelo só


class SemCota(OSError):
    """A IA chegou no limite de uso do plano. ate: quando ela libera (hora Unix), se disse."""

    def __init__(self, ate=None):
        super().__init__("chegou no limite de uso do plano")
        self.ate = ate


def chave(ia, tipo=""):
    """Onde anotar: "claude:opus" quando é o limite da semana só do Opus; "claude" quando vale pra todos."""
    if ia == "claude" and tipo in SO_DO_MODELO:
        return f"claude:{SO_DO_MODELO[tipo]}"
    return ia


def esgotar(chave_ia, ate=None, agora=None):
    """Anota que a IA chegou no limite até `ate` (ou por SEM_HORA_S, se ela não disse). Devolve a hora anotada."""
    agora = agora or time.time()
    ate = ate if ate and ate > agora else agora + SEM_HORA_S
    anotados = {c: fim for c, fim in _ler().items() if fim > agora}  # aproveita e tira os que já liberaram
    anotados[chave_ia] = ate
    salvar_json(ARQUIVO, anotados)
    return ate


def liberar(ia, modelo=""):
    """Esquece o limite dessa IA (você escolheu ela na mão: tenta de novo)."""
    anotados = _ler()
    tirados = [anotados.pop(c) for c in _chaves(ia, modelo) if c in anotados]
    if tirados:
        salvar_json(ARQUIVO, anotados)


def libera_em(ia, modelo="", agora=None):
    """A hora Unix em que essa IA volta a ter limite, ou None se ela tem limite agora."""
    agora = agora or time.time()
    anotados = _ler()
    fim = max(anotados.get(c, 0) for c in _chaves(ia, modelo))
    return fim if fim > agora else None


def quando(ate):
    """"às 15:00", "amanhã às 8:30" ou "dia 18/11 às 8:30": a hora em que a IA libera, pra falar."""
    return falar_quando(dt.datetime.fromtimestamp(ate))


def _chaves(ia, modelo):
    return [ia, f"claude:{modelo}"] if ia == "claude" and modelo else [ia]


def _ler():
    try:
        return {str(c): float(fim) for c, fim in ler_json(ARQUIVO, {}).items()}
    except (AttributeError, TypeError, ValueError):
        return {}
