"""Histórico das conversas e limpeza semanal.

- Todo dia: as conversas dos dias anteriores viram <sua pasta>/historico/AAAA-MM-DD.md (o Ultron lê se você pedir).
- A cada 7 dias: apaga do log, das sessões do Claude e das consultas dos painéis o que tem mais de 7 dias.
"""
import json
import re
import time
from pathlib import Path

from ..nucleo.claude_cli import PASTA_CONSULTAS
from ..nucleo.config import CFG, ESTADO, RAIZ
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import ARQUIVO_LOG, LOG_TRAVA, log, log_erro

DIAS_GUARDAR = 7
MARCA_LIMPEZA = ESTADO / "ultima_limpeza"


def pasta_do_claude(caminho):
    """Onde o Claude Code guarda as sessões de uma pasta (~/.claude/projects/<caminho com - no lugar de símbolos>)."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(caminho))


def _ler_log():
    try:
        with LOG_TRAVA, open(ARQUIVO_LOG, encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def exportar_historico():
    """Escreve um .md por dia (só dias que já acabaram e que ainda não têm arquivo). Nunca reescreve um dia."""
    destino = CFG["pasta"] / "historico"
    hoje = time.strftime("%Y-%m-%d")
    dias = {}
    for linha in _ler_log():
        try:
            e = json.loads(linha)
        except ValueError:
            continue
        dia = (e.get("quando") or "")[:10]
        if e.get("evento") == "turno" and e.get("voce") and dia and dia < hoje:
            dias.setdefault(dia, []).append(e)
    for dia, turnos in sorted(dias.items()):
        arquivo = destino / f"{dia}.md"
        if arquivo.exists():
            continue
        destino.mkdir(parents=True, exist_ok=True)
        partes = [f"# Conversas de {dia[8:10]}/{dia[5:7]}/{dia[:4]}\n"]
        for e in turnos:
            hora = e["quando"][11:16]
            partes.append(f"**{hora} · {CFG['nome']}:** {e.get('voce', '')}\n")
            if e.get("resposta"):
                partes.append(f"**{hora} · Ultron:** {e['resposta']}\n")
        arquivo.write_text("\n".join(partes), encoding="utf-8")
        log({"evento": "historico_salvo", "dia": dia, "turnos": len(turnos)})


def _quando(linha):
    """Data (AAAA-MM-DD) de uma linha do log. Linha estranha fica (devolve "9", que é maior que qualquer data)."""
    try:
        return (json.loads(linha).get("quando") or "9")[:10] if linha.strip().startswith("{") else "9"
    except ValueError:
        return "9"


def limpeza_semanal(forcar=False):
    try:
        ultima = float(MARCA_LIMPEZA.read_text())
    except (FileNotFoundError, ValueError):
        ultima = 0
    if not forcar and time.time() - ultima < DIAS_GUARDAR * 86400:
        return
    exportar_historico()  # antes de apagar, garante o backup
    limite_data = time.strftime("%Y-%m-%d", time.localtime(time.time() - DIAS_GUARDAR * 86400))
    # 1) log: fica só a última semana
    with LOG_TRAVA:
        try:
            linhas = ARQUIVO_LOG.read_text(encoding="utf-8").splitlines(keepends=True)
        except FileNotFoundError:
            linhas = []
        manter = [l for l in linhas if _quando(l) >= limite_data]
        temp = ARQUIVO_LOG.with_name(ARQUIVO_LOG.name + ".tmp")
        temp.write_text("".join(manter), encoding="utf-8")
        temp.replace(ARQUIVO_LOG)
    # 2) sessões antigas do Claude do Ultron e das consultas dos painéis
    apagadas = 0
    corte = time.time() - DIAS_GUARDAR * 86400
    for pasta in (pasta_do_claude(RAIZ / "cerebro"), pasta_do_claude(PASTA_CONSULTAS)):
        for arq in pasta.glob("*.jsonl") if pasta.exists() else []:
            try:
                if arq.stat().st_mtime < corte:
                    arq.unlink()
                    apagadas += 1
            except OSError:
                pass
    MARCA_LIMPEZA.write_text(str(time.time()))
    log({"evento": "limpeza", "log_removidas": len(linhas) - len(manter), "sessoes_apagadas": apagadas})
    EVENTOS.emitir({"tipo": "limpeza", "dias": DIAS_GUARDAR})  # a tela apaga as mensagens velhas do chat


def manutencao():
    """Roda de hora em hora (ver app.py)."""
    try:
        exportar_historico()
        limpeza_semanal()
    except Exception as erro:
        log_erro("limpeza_falhou", erro)
