#!/usr/bin/env python3
"""Registro das mudanças que o Ultron faz no próprio código (a pasta do projeto).

Roda em dois momentos, pelos hooks do Claude do Ultron (configurados no server.py):
  antes   (PreToolUse):  guarda uma cópia do arquivo em .estado/backups/ antes de ele mudar
  depois  (PostToolUse): escreve no MUDANCAS-ULTRON.md o pedido do dono, o arquivo, o trecho antes/depois e o
                         backup. Se for .py, confere se ainda compila e avisa o Ultron se quebrou.

O registro é automático: não depende de o Ultron lembrar. Ele só acrescenta o resumo (o que fez e por quê).
O Claude Code lê o MUDANCAS-ULTRON.md antes de mexer no projeto (ver CLAUDE.md).
"""
import json
import os
import py_compile
import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # a pasta do projeto
ESTADO = RAIZ / ".estado"
REGISTRO = RAIZ / "MUDANCAS-ULTRON.md"
BACKUPS = ESTADO / "backups"
FORA = {".estado", "cerebro", "__pycache__"}  # não é código do Ultron
CABECALHO = (
    "# Mudanças que o Ultron fez no próprio código\n\n"
    "Cada entrada é escrita sozinha pelo hook `hooks/registro.py` (pedido, arquivo, trecho e backup). "
    "Logo abaixo, o Ultron escreve o resumo do que fez e por quê.\n"
    "Pra desfazer uma mudança: copie o backup de volta por cima do arquivo.\n"
    "O Claude Code revisa este arquivo antes de mexer no projeto (veja CLAUDE.md) e marca as entradas "
    "revisadas com `Revisado pelo Claude Code`.\n"
)


def do_ultron(caminho):
    """Caminho relativo dentro da pasta do projeto, ou None se for fora (ou não for código dele)."""
    if not caminho:
        return None
    if os.name == "nt":
        caminho = re.sub(r"^/([a-zA-Z])/", r"\1:/", caminho)
    try:
        rel = Path(os.path.realpath(os.path.expanduser(caminho))).relative_to(os.path.realpath(RAIZ))
    except ValueError:
        try:  # Windows: maiúscula/minúscula
            rel = Path(os.path.normcase(os.path.realpath(caminho))).relative_to(os.path.normcase(os.path.realpath(RAIZ)))
        except ValueError:
            return None
    if not rel.parts or rel.parts[0] in FORA or rel.as_posix() == REGISTRO.name:
        return None
    return rel


def corta(texto, limite=1500):
    texto = str(texto or "")
    return texto if len(texto) <= limite else texto[:limite] + f"\n… (+{len(texto) - limite} caracteres)"


def antes(nome, entrada):
    rel = do_ultron(entrada.get("file_path") or entrada.get("notebook_path"))
    if not rel:
        return
    origem = RAIZ / rel
    BACKUPS.mkdir(parents=True, exist_ok=True)
    marca = time.strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUPS / f"{marca}_{rel.as_posix().replace('/', '__')}"
    n = 2
    while destino.exists() or destino.with_name(destino.name + ".NOVO").exists():  # duas mudanças no mesmo segundo
        destino = BACKUPS / f"{marca}-{n}_{rel.as_posix().replace('/', '__')}"
        n += 1
    if origem.exists():
        shutil.copy2(origem, destino)
    else:
        destino = destino.with_name(destino.name + ".NOVO")  # arquivo novo: desfazer = apagar
        destino.write_text("", encoding="utf-8")
    (ESTADO / "ultimo_backup.json").write_text(json.dumps({str(rel): str(destino)}), encoding="utf-8")


def depois(nome, entrada, resposta):
    rel = do_ultron(entrada.get("file_path") or entrada.get("notebook_path"))
    if not rel:
        return
    try:
        backup = json.loads((ESTADO / "ultimo_backup.json").read_text(encoding="utf-8")).get(str(rel), "")
    except (FileNotFoundError, ValueError):
        backup = ""
    try:
        pedido = (ESTADO / "pedido_atual.txt").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        pedido = ""
    partes = [f"\n## {time.strftime('%Y-%m-%d %H:%M')} · `{rel.as_posix()}` ({nome})\n"]
    if pedido:
        partes.append(f"**Pedido do dono:** {corta(pedido, 400)}\n")
    if nome in ("Edit", "MultiEdit"):
        edicoes = entrada.get("edits") or [entrada]
        for e in edicoes:
            partes.append("Antes:\n```\n" + corta(e.get("old_string")) + "\n```\nDepois:\n```\n" + corta(e.get("new_string")) + "\n```\n")
    elif nome == "Write":
        conteudo = str(entrada.get("content") or "")
        partes.append(f"Arquivo escrito inteiro ({len(conteudo.splitlines())} linhas).\n")
    if backup:
        b = Path(backup)
        partes.append(f"**Backup:** `.estado/backups/{b.name}`" + (" (arquivo era novo: desfazer = apagar)" if b.name.endswith(".NOVO") else "") + "\n")
    erro = ""
    if rel.suffix == ".py" and (RAIZ / rel).exists():
        try:
            py_compile.compile(str(RAIZ / rel), doraise=True)
            partes.append("**Compila:** sim\n")
        except py_compile.PyCompileError as e:
            erro = str(e)[-600:]
            partes.append("**Compila:** NÃO (o Ultron foi avisado)\n```\n" + erro + "\n```\n")
    partes.append("**Resumo do Ultron:** (pendente)\n")
    novo = not REGISTRO.exists()
    with open(REGISTRO, "a", encoding="utf-8") as f:
        if novo:
            f.write(CABECALHO)
        f.write("".join(partes))
    if erro:
        sys.stderr.write(
            f"REGISTRO DO ULTRON: depois da mudança, {rel.as_posix()} NÃO compila mais. O Ultron não liga assim. "
            f"Conserte agora (ou volte o backup .estado/backups/{Path(backup).name}). Erro: {erro}")
        sys.exit(2)


def main():
    try:
        dados = json.load(sys.stdin)
    except ValueError:
        return
    nome = dados.get("tool_name", "")
    if nome not in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
        return
    entrada = dados.get("tool_input") or {}
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "antes":
            antes(nome, entrada)
        else:
            depois(nome, entrada, dados.get("tool_response"))
    except SystemExit:
        raise
    except Exception as erro:  # o registro nunca pode travar o Ultron
        sys.stderr.write(f"registro.py: {erro!r}\n")


if __name__ == "__main__":
    main()
