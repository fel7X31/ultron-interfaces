#!/usr/bin/env python3
"""Registro das mudanças que o Ultron faz no próprio código (a pasta do projeto).

Roda em dois momentos:
  antes()  (chamado pela trava.py): guarda uma cópia do arquivo em .estado/backups/ antes de ele mudar
  depois() (hook PostToolUse):      escreve no MUDANCAS-ULTRON.md o pedido do dono, o arquivo, o trecho
                                    antes/depois e o backup. Se for .py, confere se ainda compila.

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

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / ".estado"
REGISTRO = RAIZ / "MUDANCAS-ULTRON.md"
BACKUPS = ESTADO / "backups"
ULTIMO_BACKUP = ESTADO / "ultimo_backup.json"
PEDIDO = ESTADO / "pedido_atual.txt"
FORA = {".estado", "cerebro", "__pycache__"}
CABECALHO = (
    "# Mudanças que o Ultron fez no próprio código\n\n"
    "Cada entrada é escrita sozinha pelo hook `hooks/registro.py` (pedido, arquivo, trecho e backup). "
    "Logo abaixo, o Ultron escreve o resumo do que fez e por quê.\n"
    "Pra desfazer uma mudança: copie o backup de volta por cima do arquivo.\n"
    "O Claude Code revisa este arquivo antes de mexer no projeto (veja CLAUDE.md) e marca as entradas "
    "revisadas com `Revisado pelo Claude Code`.\n"
)


def do_ultron(entrada):
    """O caminho do arquivo mexido, relativo à pasta do projeto, ou None se não for código do Ultron."""
    caminho = entrada.get("file_path") or entrada.get("notebook_path")
    if not caminho:
        return None
    if os.name == "nt":
        caminho = re.sub(r"^/([a-zA-Z])/", r"\1:/", caminho)
    real = os.path.realpath(os.path.expanduser(caminho))
    raiz = os.path.realpath(RAIZ)
    if not os.path.normcase(real).startswith(os.path.normcase(raiz) + os.sep):
        return None
    rel = Path(real[len(raiz) + 1:])
    if rel.parts[0] in FORA or rel.as_posix() == REGISTRO.name:
        return None
    return rel


def corta(texto, limite=1500):
    texto = str(texto or "")
    return texto if len(texto) <= limite else texto[:limite] + f"\n… (+{len(texto) - limite} caracteres)"


def ler(arquivo):
    try:
        return arquivo.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def caminho_livre(rel):
    """Um nome ainda não usado em .estado/backups/ pro backup de rel."""
    marca, nome = time.strftime("%Y-%m-%d_%H%M%S"), rel.as_posix().replace("/", "__")
    destino, n = BACKUPS / f"{marca}_{nome}", 2
    while destino.exists() or destino.with_name(destino.name + ".NOVO").exists():
        destino, n = BACKUPS / f"{marca}-{n}_{nome}", n + 1
    return destino


def antes(entrada):
    """Guarda uma cópia do arquivo antes de ele mudar (arquivo novo: um .NOVO vazio, desfazer = apagar)."""
    rel = do_ultron(entrada)
    if not rel:
        return
    BACKUPS.mkdir(parents=True, exist_ok=True)
    destino = caminho_livre(rel)
    if (RAIZ / rel).exists():
        shutil.copy2(RAIZ / rel, destino)
    else:
        destino = destino.with_name(destino.name + ".NOVO")
        destino.write_text("", encoding="utf-8")
    ULTIMO_BACKUP.write_text(json.dumps({str(rel): str(destino)}), encoding="utf-8")


def backup_de(rel):
    try:
        return json.loads(ULTIMO_BACKUP.read_text(encoding="utf-8")).get(str(rel), "")
    except (FileNotFoundError, ValueError):
        return ""


def erro_de_compilacao(rel):
    """O erro, se rel for um .py que não compila mais; senão ""."""
    try:
        py_compile.compile(str(RAIZ / rel), doraise=True)
        return ""
    except py_compile.PyCompileError as erro:
        return str(erro)[-600:]


def trechos(nome, entrada):
    """O antes/depois de cada edição, ou o tamanho do arquivo escrito."""
    if nome == "Write":
        return f"Arquivo escrito inteiro ({len(str(entrada.get('content') or '').splitlines())} linhas).\n"
    if nome not in ("Edit", "MultiEdit"):
        return ""
    return "".join(f"Antes:\n```\n{corta(e.get('old_string'))}\n```\nDepois:\n```\n{corta(e.get('new_string'))}\n```\n"
                   for e in entrada.get("edits") or [entrada])


def compilacao(rel):
    """A linha "Compila" do registro e o erro (vazio se compilou ou se não é .py)."""
    if rel.suffix != ".py" or not (RAIZ / rel).exists():
        return "", ""
    erro = erro_de_compilacao(rel)
    if not erro:
        return "**Compila:** sim\n", ""
    return f"**Compila:** NÃO (o Ultron foi avisado)\n```\n{erro}\n```\n", erro


def anotar(texto):
    """Acrescenta no MUDANCAS-ULTRON.md (com o cabeçalho, se o arquivo ainda não existe)."""
    novo = not REGISTRO.exists()
    with open(REGISTRO, "a", encoding="utf-8") as f:
        f.write((CABECALHO if novo else "") + texto)


def depois(nome, entrada):
    """Anota a mudança no MUDANCAS-ULTRON.md e avisa o Ultron se o .py quebrou."""
    rel = do_ultron(entrada)
    if not rel:
        return
    pedido, backup = ler(PEDIDO), backup_de(rel)
    linha_compila, erro = compilacao(rel)
    texto = f"\n## {time.strftime('%Y-%m-%d %H:%M')} · `{rel.as_posix()}` ({nome})\n"
    if pedido:
        texto += f"**Pedido do dono:** {corta(pedido, 400)}\n"
    texto += trechos(nome, entrada)
    if backup:
        era_novo = " (arquivo era novo: desfazer = apagar)" if backup.endswith(".NOVO") else ""
        texto += f"**Backup:** `.estado/backups/{Path(backup).name}`{era_novo}\n"
    anotar(texto + linha_compila + "**Resumo do Ultron:** (pendente)\n")
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
    try:
        depois(nome, dados.get("tool_input") or {})
    except SystemExit:
        raise
    except Exception as erro:
        sys.stderr.write(f"registro.py: {erro!r}\n")


if __name__ == "__main__":
    main()
