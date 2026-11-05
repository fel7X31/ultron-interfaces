"""Pré-busca: pergunta que bate com um gatilho do gatilhos.json já vai pro Claude com o dado buscado.

O atalho roda enquanto a pergunta sai, e o Claude só precisa falar. Pra criar um gatilho novo, basta uma entrada
no gatilhos.json: {"nome": ..., "palavras": [...], "comando": ["script.py", "args"], "periodo": true/false}.
"""
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from ..nucleo.arquivos import ler_json
from ..nucleo.config import ATALHOS, RAIZ
from ..nucleo.texto import normalizar

GATILHOS = ler_json(RAIZ / "gatilhos.json", []) or []


def periodo_falado(texto):
    """"da semana" / "do mês" / "de ontem" -> argumentos que os atalhos entendem."""
    t = " ".join(normalizar(texto))
    if re.search(r"\b(semana|ultimos dias|7 dias|sete dias)\b", t):
        return ["--ultimos", "7"]
    if re.search(r"\b(mes|30 dias|trinta dias)\b", t):
        return ["--ultimos", "30"]
    if re.search(r"\bontem\b", t):
        return ["--dia", "ontem"]
    return ["--dia", "hoje"]


def _comandos(texto):
    palavras = set(normalizar(texto))
    for g in GATILHOS:
        alvos = {" ".join(normalizar(p)) for p in g.get("palavras", [])}
        if palavras & alvos:
            cmd = [sys.executable, str(ATALHOS / g["comando"][0])] + g["comando"][1:]
            if g.get("periodo"):
                cmd += periodo_falado(texto)
            yield g["nome"], cmd


def _rodar(item):
    nome, cmd = item
    try:
        r = subprocess.run(cmd, cwd=str(RAIZ), capture_output=True, text=True, timeout=8)
        return f"{nome}: {r.stdout.strip()}" if r.returncode == 0 and r.stdout.strip() else ""
    except Exception:
        return ""


def prebusca(texto):
    """Texto pra juntar à pergunta (ou "" se nenhum gatilho bateu)."""
    comandos = list(_comandos(texto))
    if not comandos:
        return ""
    with ThreadPoolExecutor(max_workers=len(comandos)) as grupo:
        linhas = [l for l in grupo.map(_rodar, comandos) if l]
    if not linhas:
        return ""
    return ("\n\n[dados que o Ultron já buscou agora pra esta pergunta. Responda direto com eles, "
            "sem rodar comando e sem aviso. Só rode algo se faltar o que ele pediu:]\n" + "\n".join(linhas))
