#!/usr/bin/env python3
"""Trava do Ultron: roda antes de cada ferramenta que o Claude usa.

Ler, buscar e consultar passa direto. Publicar, enviar mensagem, apagar,
mexer em cliente ou escrever fora da pasta de trabalho só passa se você
confirmou por voz (o servidor cria o arquivo .estado/confirmado durante
aquele pedido). Sem confirmação, a ação é barrada e o Claude é orientado a
perguntar "Confirma?".

Não é uma caixa de areia: é uma lista de proteção. Leia antes de liberar
ferramentas novas.
"""
import json
import os
import re
import sys
from pathlib import Path

LIVRES = {
    "Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoWrite", "Skill", "Task", "Agent",
    "ToolSearch", "ListMcpResourcesTool", "ReadMcpResourceTool", "BashOutput", "KillShell",
}

# Palavras no nome da ferramenta de um conector (MCP)
MCP_ARRISCADO = re.compile(
    r"(send|enviar|envio|criar|create|salvar|save|update|atualizar|anotar|delete|excluir|trash|apagar|"
    r"publicar|publish|tirar_do_ar|arquivar|cancelar|editar|edit|upload|move|mover|share|reply|forward|"
    r"draft|label|spam|respond|transfer|provision|set_|add_|remove|apply|dub|duplicate|generate|reencode|"
    r"schedule|rename|enable|disable|finish|start_|onboarding|import|write|copy|merge|comment|resolve)",
    re.I,
)
MCP_LEITURA = re.compile(
    r"(list|listar|get|ver|buscar|search|read|ficha|metricas|quem_sou|quadro|assinantes|"
    r"suggest|count|status|show|preview|who_am_i|find|info|help|query|fetch|download_file_content)",
    re.I,
)

# Comandos de terminal que mudam coisas fora (ou apagam)
BASH_ARRISCADO = [
    r"\brm\b", r"\bmv\b", r"\bsudo\b", r"\bkill(all)?\b", r"\bpkill\b", r"\bchmod\b", r"\bchown\b",
    r"\bgit\s+(push|reset|clean|checkout|rebase|commit|merge)\b",
    r"\bcurl\b.*\s-X\s*(POST|PUT|PATCH|DELETE)\b", r"\bcurl\b.*\s(-d|--data\S*|-F|--form|-T|--upload-file)\b",
    r"\bnpm\s+publish\b", r"\bvercel\b", r"\bsupabase\b.*\b(delete|reset|push)\b",
    r"\bgh\s+\w+\s+(create|delete|merge|edit|close|comment)\b", r"\bosascript\b", r"\bdd\b", r"\btee\b",
]
# Zernio (redes sociais): só consulta passa direto
ZERNIO_LEITURA = {"check", "status", "accounts", "yt-playlists", "tiktok-info", "li-orgs", "posts",
                  "post-get", "autos", "auto-get", "auto-logs"}


def barrar(oque):
    sys.stderr.write(
        f"TRAVA DO ULTRON: {oque} precisa da confirmação do dono por voz. Não execute agora e não tente "
        "outro caminho pra fazer a mesma coisa. Responda em uma frase dizendo exatamente o que vai fazer "
        "e termine com 'Confirma?'. Quando ele confirmar (ou já tiver dado permissão no pedido), a trava abre "
        "sozinha naquele pedido: aí é só fazer de novo."
    )
    sys.exit(2)


RAIZ = Path(__file__).resolve().parent.parent  # a pasta do projeto
PASTA = re.escape(RAIZ.name)                    # o nome dela (jarvis, ultron...), pras regras de terminal abaixo


def protegido(caminho):
    """hooks/ e .env do Ultron: ele nunca escreve neles."""
    if not caminho:
        return False
    if os.name == "nt":
        caminho = re.sub(r"^/([a-zA-Z])/", r"\1:/", caminho)
    real = os.path.normcase(os.path.realpath(os.path.expanduser(caminho)))
    raiz = os.path.normcase(os.path.realpath(RAIZ))
    return real.startswith(os.path.join(raiz, "hooks") + os.sep) or real == os.path.join(raiz, ".env")


def mexe_em_protegido(cmd):
    """Comando de terminal que cita a trava/registro/.env do Ultron e não é só leitura."""
    if not re.search(rf"(trava\.py|registro\.py|{PASTA}[/\\]+hooks|{PASTA}[/\\]+\.env)", cmd, re.I):
        return False
    return bool(re.search(r"(>|\bsed\s+-i|\bcp\b|\bmv\b|\brm\b|\btee\b|\bpython\S*\s+-c|Set-Content|Out-File|"
                          r"Remove-Item|Move-Item|Copy-Item|\bdel\b|\btruncate\b|\bperl\b)", cmd, re.I))


def escreve_no_codigo(cmd):
    """Comando de terminal que escreve em arquivo do Ultron (a pasta do projeto, fora de .estado): só via Edit/Write."""
    if not re.search(rf"{PASTA}([/\\]|\"|'|\s|$)", cmd, re.I) and \
            not re.search(r"\b(server|palmas|curriculo)\.py\b|persona\.md|web[/\\]|ultron[/\\]|tests[/\\]", cmd):
        return False
    so_estado = re.search(rf"{PASTA}[/\\]+\.estado", cmd) and not re.search(rf"{PASTA}[/\\]+(?!\.estado)\w", cmd)
    if so_estado:
        return False
    return bool(re.search(r"(>(?!\s*/dev/null|&)|\bsed\s+-i|\bcp\b|\bmv\b|\brm\b|\bdel\b|\btee\b|Set-Content|Out-File|"
                          r"Move-Item|Copy-Item|Remove-Item|\btruncate\b|\bperl\s+-\w*i|\.write_text|open\([^)]*['\"][wa])",
                          cmd, re.I))


def proibido():
    sys.stderr.write(
        "TRAVA DO ULTRON: a trava (pasta hooks) e o .env do Ultron não podem ser mudados pelo Ultron, nem com "
        "confirmação. Não tente outro caminho. Diga ao dono, em uma frase, que isso se muda no Claude Code."
    )
    sys.exit(2)


def redireciona_pra_fora(cmd, pasta):
    """Escreve num arquivo com > ou >> fora da pasta de trabalho? (dentro dela é como usar o Write: passa)."""
    base = re.search(r"\bcd\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    base = base.group(1).strip("\"'") if base else ""
    for alvo in re.findall(r"(?<![0-9&<])>{1,2}\s*(\"[^\"]+\"|'[^']+'|[^\s;&|]+)", cmd):
        alvo = alvo.strip("\"'")
        if alvo in ("/dev/null", "&1", "&2", "NUL", "nul"):
            continue
        alvo = alvo.replace("$HOME", os.path.expanduser("~"))
        if not os.path.isabs(os.path.expanduser(alvo)) and base:
            alvo = os.path.join(base, alvo)
        if not dentro_da_pasta(alvo, pasta):
            return True
    return False


def zernio_arriscado(cmd):
    m = re.search(r"zernio\.py\s+(\S+)(?:\s+(\S+))?", cmd)
    if not m:
        return False
    sub, metodo = m.group(1), (m.group(2) or "").upper()
    if sub == "api":
        return metodo != "GET"
    return sub not in ZERNIO_LEITURA


def dentro_da_pasta(caminho, pasta):
    if not caminho or not pasta:
        return False
    if os.name == "nt":  # Git Bash escreve /c/Users/...
        caminho = re.sub(r"^/([a-zA-Z])/", r"\1:/", caminho)
    # normcase: no Windows "C:/users/..." e "C:\Users\..." são a mesma pasta
    real =os.path.normcase(os.path.realpath(os.path.expanduser(caminho)))
    pasta = os.path.normcase(pasta)
    return real == pasta or real.startswith(pasta.rstrip(os.sep) + os.sep)


def main():
    try:
        dados = json.load(sys.stdin)
    except ValueError:
        return
    nome = dados.get("tool_name", "")
    entrada = dados.get("tool_input") or {}
    # JARVIS_*: nome antigo, de um servidor que ainda não foi religado depois da troca de nome
    var_estado = os.environ.get("ULTRON_ESTADO") or os.environ.get("JARVIS_ESTADO", "")
    var_pasta = os.environ.get("ULTRON_PASTA") or os.environ.get("JARVIS_PASTA", "")
    estado = Path(var_estado)
    pasta = os.path.realpath(var_pasta) if var_pasta else ""
    confirmado = bool(var_estado) and (estado / "confirmado").exists()

    # A trava e as chaves nunca: nem com confirmação (senão ele poderia desligar a própria proteção).
    if nome in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if protegido(entrada.get("file_path") or entrada.get("notebook_path") or ""):
            proibido()
    if nome == "Bash" and mexe_em_protegido(entrada.get("command", "")):
        proibido()
    if nome == "Bash" and escreve_no_codigo(entrada.get("command", "")):
        sys.stderr.write(
            "TRAVA DO ULTRON: pra mudar o código do Ultron use só as ferramentas Edit ou Write (elas guardam backup e "
            "registram a mudança no MUDANCAS-ULTRON.md). Não use o terminal pra isso.")
        sys.exit(2)

    if nome in LIVRES:
        return
    if confirmado:
        return

    if nome.startswith("mcp__"):
        acao = nome.split("__")[-1]
        if MCP_ARRISCADO.search(acao) or not MCP_LEITURA.search(acao):
            barrar(f"a ação '{acao}'")
        return

    if nome in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        caminho = entrada.get("file_path") or entrada.get("notebook_path") or ""
        if not dentro_da_pasta(caminho, pasta):
            barrar("escrever fora da pasta de trabalho")
        return

    if nome == "Bash":
        cmd = entrada.get("command", "")
        if zernio_arriscado(cmd):
            barrar("publicar, agendar ou mudar algo nas redes sociais")
        if any(re.search(p, cmd) for p in BASH_ARRISCADO) or redireciona_pra_fora(cmd, pasta):
            barrar("esse comando de terminal")
        return


if __name__ == "__main__":
    main()
