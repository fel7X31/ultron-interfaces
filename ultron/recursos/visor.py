"""Visor: mostra na tela do Ultron uma foto, um PDF ou um texto (do computador ou de um link da internet).

`mostrar(origem)` confere o que é, guarda o arquivo numa lista curta e avisa a tela. A tela abre o arquivo por
/api/arquivo/<id>: só entram nessa lista arquivos que o próprio Ultron mandou mostrar, nunca um caminho qualquer.
"""
import mimetypes
import secrets
import urllib.parse
from collections import OrderedDict
from pathlib import Path

from ..nucleo.eventos import EVENTOS

IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
TEXTOS = {".txt", ".md", ".csv", ".json", ".log"}
LIMITE_BYTES = 40 * 1024 * 1024
MAXIMO_NA_LISTA = 30
_ARQUIVOS = OrderedDict()  # id -> Path


def _tipo_do(sufixo):
    if sufixo in IMAGENS:
        return "imagem"
    if sufixo == ".pdf":
        return "pdf"
    if sufixo in TEXTOS:
        return "texto"
    return ""


def mostrar(origem):
    """Prepara o item e avisa a tela. Devolve {"tipo", "url", "nome"}. ValueError = não dá pra mostrar."""
    origem = (origem or "").strip().strip('"')
    if not origem:
        raise ValueError("Falta dizer o que mostrar.")
    if origem.lower().startswith(("http://", "https://")):
        nome = Path(urllib.parse.unquote(urllib.parse.urlsplit(origem).path)).name or "imagem da internet"
        item = {"tipo": "imagem", "url": origem, "nome": nome}  # a tela carrega direto da internet
    else:
        arquivo = Path(origem).expanduser()
        if not arquivo.is_file():
            raise ValueError("Não achei esse arquivo.")
        tipo = _tipo_do(arquivo.suffix.lower())
        if not tipo:
            raise ValueError("Esse tipo de arquivo eu não sei mostrar na tela.")
        if arquivo.stat().st_size > LIMITE_BYTES:
            raise ValueError("Esse arquivo é grande demais pra mostrar na tela.")
        id_arquivo = secrets.token_urlsafe(8)
        _ARQUIVOS[id_arquivo] = arquivo.resolve()
        while len(_ARQUIVOS) > MAXIMO_NA_LISTA:
            _ARQUIVOS.popitem(last=False)
        item = {"tipo": tipo, "url": f"/api/arquivo/{id_arquivo}", "nome": arquivo.name}
    EVENTOS.emitir({"tipo": "visor", "item": item})
    return item


def ler(id_arquivo):
    """(bytes, tipo MIME) de um arquivo já registrado, ou None."""
    arquivo = _ARQUIVOS.get(id_arquivo)
    if not arquivo or not arquivo.is_file():
        return None
    tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
    if tipo.startswith("text/") or arquivo.suffix.lower() in TEXTOS:
        tipo = "text/plain; charset=utf-8"
    return arquivo.read_bytes(), tipo
