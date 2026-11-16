#!/usr/bin/env python3
"""Trava do Ultron: roda antes de cada ferramenta que o Claude usa.

Passa direto: ler, buscar, pesquisar, abrir e controlar o PC, e criar ou editar arquivos em qualquer lugar da
pasta do usuário (inclusive o código do próprio Ultron, que ganha backup e registro). O dono autoriza isso tudo.

Só com a confirmação dele por voz (o servidor cria o arquivo .estado/confirmado durante aquele pedido): apagar,
enviar mensagem ou dados pra fora, publicar, mexer em agenda/e-mail, git push, desligar o PC e escrever fora da
pasta do usuário ou nas pastas de configuração (AppData e as que começam com ponto). Sem confirmação, a ação é
barrada, fica anotada em .estado/trava.jsonl e o Claude é orientado a perguntar "Confirma?".

A trava (hooks/) e o .env o Ultron nunca muda, nem com confirmação.

Com ULTRON_CONFIRMAR=0 (o padrão: o dono autorizou tudo), nada pede confirmação; só a trava e o .env continuam fora.

Não é uma caixa de areia: é uma lista de proteção. Leia antes de liberar ferramentas novas.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

LIVRES = {
    "Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoWrite", "Skill", "Task", "Agent",
    "ToolSearch", "ListMcpResourcesTool", "ReadMcpResourceTool", "BashOutput", "KillShell",
}
ESCRITA = ("Write", "Edit", "MultiEdit", "NotebookEdit")

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

# Comandos de terminal que apagam, matam programa, desligam o PC ou mexem em repositório e publicação
BASH_ARRISCADO = [
    r"\brm\b", r"\brmdir\b", r"\bdel\b", r"\brd\b", r"Remove-Item", r"Clear-Content", r"\bformat\s+[a-z]:",
    r"\bdiskpart\b", r"\bsudo\b", r"\bkill(all)?\b", r"\bpkill\b", r"\btaskkill\b", r"Stop-Process",
    r"\bchmod\b", r"\bchown\b", r"\bshutdown\b", r"Stop-Computer", r"Restart-Computer", r"\breg\s+(add|delete)\b",
    r"\bgit\s+(push|reset|clean|checkout|rebase|commit|merge)\b",
    r"\bnpm\s+publish\b", r"\bvercel\b", r"\bsupabase\b.*\b(delete|reset|push)\b",
    r"\bgh\s+\w+\s+(create|delete|merge|edit|close|comment)\b", r"\bosascript\b", r"\bdd\b",
]
# Zernio (redes sociais): só consulta passa direto
ZERNIO_LEITURA = {"check", "status", "accounts", "yt-playlists", "tiktok-info", "li-orgs", "posts",
                  "post-get", "autos", "auto-get", "auto-logs"}


def barrar(oque, nome="", entrada=None):
    anotar_barrado(oque, nome, entrada)
    sys.stderr.write(
        f"TRAVA DO ULTRON: {oque} precisa da confirmação do dono por voz. Não execute agora e não tente "
        "outro caminho pra fazer a mesma coisa. Responda em uma frase dizendo exatamente o que vai fazer "
        "e termine com 'Confirma?'. Quando ele confirmar (ou já tiver dado permissão no pedido), a trava abre "
        "sozinha naquele pedido: aí é só fazer de novo."
    )
    sys.exit(2)


def anotar_barrado(oque, nome, entrada):
    """Uma linha em .estado/trava.jsonl pra cada ação barrada: dá pra ver depois o que a trava segurou."""
    estado = os.environ.get("ULTRON_ESTADO") or os.environ.get("JARVIS_ESTADO", "")
    if not estado:
        return
    linha = {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "motivo": oque, "ferramenta": nome,
             "entrada": json.dumps(entrada or {}, ensure_ascii=False)[:300]}
    try:
        with open(Path(estado) / "trava.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError:
        pass


def proibido():
    sys.stderr.write(
        "TRAVA DO ULTRON: a trava (pasta hooks) e o .env do Ultron não podem ser mudados pelo Ultron, nem com "
        "confirmação. Não tente outro caminho. Diga ao dono, em uma frase, que isso se muda no Claude Code."
    )
    sys.exit(2)


RAIZ = Path(__file__).resolve().parent.parent  # a pasta do projeto
PASTA = re.escape(RAIZ.name)                    # o nome dela (jarvis, ultron...), pras regras de terminal abaixo


def caminho_real(caminho):
    """O caminho completo e comparável (Git Bash escreve /c/Users/...; no Windows a caixa não importa)."""
    if os.name == "nt":
        caminho = re.sub(r"^/([a-zA-Z])/", r"\1:/", caminho)
    return os.path.normcase(os.path.realpath(os.path.expanduser(caminho)))


def protegido(caminho):
    """hooks/ e .env do Ultron: ele nunca escreve neles."""
    if not caminho:
        return False
    real, raiz = caminho_real(caminho), caminho_real(str(RAIZ))
    return real.startswith(os.path.join(raiz, "hooks") + os.sep) or real == os.path.join(raiz, ".env")


def mexe_em_protegido(cmd):
    """Comando de terminal que cita a trava/registro/.env do Ultron e não é só leitura."""
    if not re.search(rf"(trava\.py|registro\.py|{PASTA}[/\\]+hooks|{PASTA}[/\\]+\.env)", cmd, re.I):
        return False
    return bool(re.search(r"(>|\bsed\s+-i|\bcp\b|\bmv\b|\brm\b|\btee\b|\bpython\S*\s+-c|Set-Content|Out-File|"
                          r"Add-Content|New-Item|Remove-Item|Move-Item|Copy-Item|Clear-Content|WriteAll|AppendAll|"
                          r"\bdel\b|\btruncate\b|\bperl\b)", cmd, re.I))


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


def guardar_backup(nome, entrada):
    """Escrita no próprio código do Ultron: guarda uma cópia antes (o registro.py anota depois)."""
    if nome not in ESCRITA:
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import registro
        registro.antes(entrada)
    except Exception as erro:
        sys.stderr.write(f"backup falhou: {erro!r}\n")


def pode_escrever(caminho, pasta):
    """Escrever aqui passa sem perguntar? Sim na pasta de trabalho e em qualquer lugar da pasta do usuário
    (Desktop, Documentos, Downloads, o código do Ultron...), menos nas pastas de configuração: AppData e as que
    começam com ponto (.claude, .ssh, .config...). Fora da pasta do usuário (pastas do Windows), não."""
    if not caminho:
        return False
    if dentro_da_pasta(caminho, pasta):
        return True
    casa, real = caminho_real("~"), caminho_real(caminho)
    if not real.startswith(casa.rstrip(os.sep) + os.sep):
        return False
    primeira = real[len(casa.rstrip(os.sep)) + 1:].split(os.sep)[0]
    return not (primeira.startswith(".") or primeira == os.path.normcase("AppData"))


def redireciona_pra_fora(cmd, pasta):
    """Escreve num arquivo com > ou >> onde não pode escrever sem perguntar (veja pode_escrever)?"""
    base = re.search(r"\bcd\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    base = base.group(1).strip("\"'") if base else ""
    for alvo in re.findall(r"(?<![0-9&<])>{1,2}\s*(\"[^\"]+\"|'[^']+'|[^\s;&|]+)", cmd):
        alvo = alvo.strip("\"'")
        if alvo in ("/dev/null", "&1", "&2", "NUL", "nul"):
            continue
        alvo = alvo.replace("$HOME", os.path.expanduser("~"))
        if not os.path.isabs(os.path.expanduser(alvo)) and base:
            alvo = os.path.join(base, alvo)
        if not pode_escrever(alvo, pasta):
            return True
    return False


def envia_dados(cmd):
    """curl que manda dados pra fora: POST, PUT, DELETE, formulário ou upload. Busca (GET, inclusive com -G e
    --data-urlencode) passa, e pedido pro próprio Ultron (localhost) também."""
    for trecho in re.findall(r"\bcurl\b[^|;&]*", cmd):
        if re.search(r"https?://(localhost|127\.0\.0\.1)\b", trecho):
            continue
        if re.search(r"\s-X\s*(POST|PUT|PATCH|DELETE)\b|\s(-F|--form|-T|--upload-file)\b", trecho):
            return True
        if re.search(r"\s(-d|--data\S*)\b", trecho) and not re.search(r"\s(-G|--get)\b", trecho):
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
    real, pasta = caminho_real(caminho), os.path.normcase(pasta)
    return real == pasta or real.startswith(pasta.rstrip(os.sep) + os.sep)


def main():
    sys.stderr.reconfigure(encoding="utf-8")  # o Claude lê a mensagem em UTF-8; o padrão do Windows quebra os acentos
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
    autorizou_tudo = os.environ.get("ULTRON_CONFIRMAR") == "0"  # o dono liberou tudo: nada pede confirmação
    cmd = entrada.get("command", "") if nome == "Bash" else ""

    # A trava e as chaves nunca: nem com confirmação (senão ele poderia desligar a própria proteção).
    if nome in ESCRITA and protegido(entrada.get("file_path") or entrada.get("notebook_path") or ""):
        proibido()
    if cmd and mexe_em_protegido(cmd):
        proibido()
    if cmd and escreve_no_codigo(cmd):
        sys.stderr.write(
            "TRAVA DO ULTRON: pra mudar o código do Ultron use só as ferramentas Edit ou Write (elas guardam backup e "
            "registram a mudança no MUDANCAS-ULTRON.md). Não use o terminal pra isso.")
        sys.exit(2)

    if nome in LIVRES:
        return
    if confirmado or autorizou_tudo:
        guardar_backup(nome, entrada)
        return

    if nome.startswith("mcp__"):
        acao = nome.split("__")[-1]
        if MCP_ARRISCADO.search(acao) or not MCP_LEITURA.search(acao):
            barrar(f"a ação '{acao}'", nome, entrada)
        return

    if nome in ESCRITA:
        if not pode_escrever(entrada.get("file_path") or entrada.get("notebook_path") or "", pasta):
            barrar("escrever fora da sua pasta de usuário ou numa pasta de configuração", nome, entrada)
        guardar_backup(nome, entrada)
        return

    if nome == "Bash":
        if zernio_arriscado(cmd):
            barrar("publicar, agendar ou mudar algo nas redes sociais", nome, entrada)
        if envia_dados(cmd):
            barrar("mandar dados pra fora da internet", nome, entrada)
        if any(re.search(p, cmd) for p in BASH_ARRISCADO) or redireciona_pra_fora(cmd, pasta):
            barrar("esse comando de terminal (apaga, fecha à força, desliga ou mexe fora da pasta do usuário)",
                   nome, entrada)
        return


if __name__ == "__main__":
    main()
