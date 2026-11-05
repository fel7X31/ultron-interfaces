"""Funções de texto usadas em vários lugares."""
import json
import re
import unicodedata


def normalizar(texto):
    """Minúsculo, sem acento e sem pontuação, em palavras: "Próxima música!" -> ["proxima", "musica"]."""
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", sem_acento).split()


def limpar_para_fala(texto):
    """Tira markdown, links e listas pra o texto soar bem em voz alta."""
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)  # [link](url) -> link
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"[*_#`>|]", "", texto)
    texto = re.sub(r"^\s*[-•]\s*", "", texto, flags=re.M)
    texto = " ".join(texto.split())
    return texto[:700]


def json_do_texto(texto):
    """Pega o primeiro {...} de um texto (o Claude às vezes escreve algo antes/depois do JSON)."""
    return json.loads(texto[texto.index("{"):texto.rindex("}") + 1])
