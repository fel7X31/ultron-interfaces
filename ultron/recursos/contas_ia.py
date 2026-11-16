"""Outras IAs pela sua própria conta, sem chave de API: o Gemini pelo Gemini CLI (entra com o Google) e o ChatGPT
pelo Codex (entra com a conta do ChatGPT). São programas de terminal, como o Claude Code que o Ultron já usa.

Instalar (uma vez): npm install -g @google/gemini-cli @openai/codex
Entrar: o botão "Entrar" da lista de IAs abre o login de cada um (o navegador abre pra você entrar).
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..nucleo.config import ESTADO
from .limites import SemCota

PASTA_VAZIA = ESTADO / "ias"  # elas rodam aqui dentro: não leem nem mexem nos seus arquivos
INSTALAR = "npm install -g @google/gemini-cli @openai/codex"
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MESES = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
ACABOU = re.compile(r"usage limit|quota|resource_exhausted|\b429\b", re.I)  # o programa disse que a conta chegou no limite
LIBERA = re.compile(r"try again at (?:([a-z]{3})[a-z]* (\d{1,2})[a-z]*,? (\d{4}),? )?(\d{1,2}):(\d{2}) ?([ap]m)", re.I)
CONTAS = {  # ia -> o programa, onde ele guarda o login, o comando de entrar e com o quê
    "gemini": {"programa": "gemini", "login": "~/.gemini/oauth_creds.json", "entrar": ["gemini"], "com": "Google"},
    "chatgpt": {"programa": "codex", "login": "~/.codex/auth.json", "entrar": ["codex", "login"], "com": "ChatGPT"},
}


def instalado(ia):
    return ia in CONTAS and bool(shutil.which(CONTAS[ia]["programa"]))


def conectado(ia):
    """O programa está instalado e você já entrou com a sua conta?"""
    return instalado(ia) and Path(CONTAS[ia]["login"]).expanduser().exists()


def entrar(ia):
    """Abre uma janela do terminal com o login da IA. ValueError se ela não entra por conta ou falta instalar."""
    if ia not in CONTAS:
        raise ValueError("Essa IA só funciona com chave no .env.")
    if not instalado(ia):
        raise ValueError(f"Falta instalar o programa dela. No terminal: {INSTALAR}")
    subprocess.Popen(["cmd", "/c", "start", f"Entrar com {CONTAS[ia]['com']}", "cmd", "/k", *CONTAS[ia]["entrar"]],
                     creationflags=SEM_JANELA)


def perguntar(ia, mensagens, modelo="", limite=120, esforco=""):
    """Manda a conversa pro programa da IA e devolve o texto da resposta."""
    texto = _conversa_em_texto(mensagens)
    if ia == "gemini":
        return _perguntar_ao_gemini(texto, modelo, limite)
    return _perguntar_ao_codex(texto, modelo, limite, esforco)


def _perguntar_ao_gemini(texto, modelo, limite):
    saida = _rodar([shutil.which("gemini"), "--output-format", "json", *(["-m", modelo] if modelo else [])],
                   texto, limite)
    try:
        return json.loads(saida)["response"].strip()
    except (ValueError, KeyError, TypeError):
        return saida.strip()


def _perguntar_ao_codex(texto, modelo, limite, esforco=""):
    with tempfile.TemporaryDirectory() as pasta:
        resposta = Path(pasta) / "resposta.txt"
        _rodar([shutil.which("codex"), "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
                "-o", str(resposta), *(["-m", modelo] if modelo else []),
                *(["-c", f"model_reasoning_effort={esforco}"] if esforco else []), "-"], texto, limite)
        return resposta.read_text(encoding="utf-8").strip()


def _rodar(cmd, entrada, limite):
    """Roda o programa com a conversa pela entrada padrão (cabe texto grande) e devolve o que ele escreveu."""
    PASTA_VAZIA.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=limite,
                       cwd=str(PASTA_VAZIA), creationflags=SEM_JANELA)
    if r.returncode != 0:
        erro = (r.stderr or r.stdout).strip()
        if ACABOU.search(erro):
            raise SemCota(_libera_em(erro))
        raise OSError(erro[-300:])
    return r.stdout


def _libera_em(erro, hoje=None):
    """A hora Unix do "try again at Nov 18th, 2026 8:30 AM" (ou só "8:30 AM", quando é hoje) que o Codex escreve."""
    m = LIBERA.search(erro)
    if not m or (m.group(1) and m.group(1).title() not in MESES):
        return None
    mes, dia, ano, hora, minuto, periodo = m.groups()
    data = dt.date(int(ano), MESES[mes.title()], int(dia)) if mes else (hoje or dt.date.today())
    hora = int(hora) % 12 + (12 if periodo.lower() == "pm" else 0)
    return dt.datetime.combine(data, dt.time(hora, int(minuto))).timestamp()


def _conversa_em_texto(mensagens):
    """A conversa no formato de chat ({"role", "content"}) num texto só, que é o que esses programas recebem."""
    quem = {"system": "INSTRUÇÕES", "user": "ELE", "assistant": "VOCÊ"}
    partes = [f"[{quem[m['role']]}]\n{m['content']}" for m in mensagens]
    partes.append("Responda agora só a sua próxima fala, como VOCÊ, sem usar ferramentas.")
    return "\n\n".join(partes)
