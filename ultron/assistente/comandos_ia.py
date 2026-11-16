"""Comandos de voz pra escolher quem responde: "usa o Gemini", "muda pro ChatGPT", "volta pro Claude", "usa o Opus"."""
import re

from . import cerebro
from .comandos import comando

TROCAR = re.compile(r"\b(usa|use|usar|muda|mude|mudar|troca|troque|trocar|volta|volte|voltar|passa|passe|"
                    r"coloca|bota|pode usar)\b")
QUAL = re.compile(r"\b(qual|que) (ia|inteligencia|modelo|cerebro)\b.*\b(usando|respondendo|rodando|agora)\b")
IAS = [  # (nome falado, ia, modelo do Claude). A transcrição escreve "Cloud" no lugar de Claude.
    (re.compile(r"\bchat ?gpt\b|\bgpt\b"), "chatgpt", ""),
    (re.compile(r"\b(gemini|gemine|jemini)\b"), "gemini", ""),
    (re.compile(r"\b(grok|groc|groque)\b"), "grok", ""),
    (re.compile(r"\bopus\b"), "claude", "opus"),
    (re.compile(r"\b(sonnet|sonet|soneto)\b"), "claude", "sonnet"),
    (re.compile(r"\b(haiku|haicai|raiku)\b"), "claude", "haiku"),
    (re.compile(r"\b(claude|claud|cloud|clod)\b"), "claude", ""),
]


@comando
def escolher_ia(fala):
    if not fala.curta(9):
        return None
    if QUAL.search(fala.frase):
        return f"Agora quem responde é o {cerebro.nome_atual()}."
    if not TROCAR.search(fala.frase):
        return None
    for regex, ia, modelo in IAS:
        if regex.search(fala.frase):
            try:
                nome = cerebro.escolher(ia, modelo)
            except ValueError as erro:
                return str(erro)
            fala.registro["ia"] = nome
            return f"Feito. Agora quem responde é o {nome}."
    return None
