"""Consultas de uma vez só ao Claude Code (`claude -p`), fora da conversa principal.

Usado pelos painéis (e-mails, agenda), pela avaliação das tarefas etc. Roda numa pasta vazia,
então não carrega o CLAUDE.md nem a memória da sua pasta, e só com as ferramentas que você liberar.
"""
import json
import os
import shutil
import subprocess

from .config import ESTADO
from .texto import json_do_texto

PASTA_CONSULTAS = ESTADO / "paineis-claude"


def claude_bin():
    return shutil.which("claude") or "claude"


def claude_json(pedido, ferramentas, limite=150, modelo="sonnet"):
    """Manda o pedido, espera a resposta e devolve o JSON que veio nela (levanta erro se não veio JSON)."""
    PASTA_CONSULTAS.mkdir(parents=True, exist_ok=True)
    cmd = [claude_bin(), "-p", pedido, "--model", modelo, "--allowedTools", ferramentas, "--output-format", "json"]
    r = subprocess.run(cmd, cwd=str(PASTA_CONSULTAS), capture_output=True, text=True, encoding="utf-8",
                       timeout=limite, env=os.environ.copy())
    return json_do_texto(json.loads(r.stdout).get("result", ""))
