"""O básico da tela: eventos ao vivo, áudio das falas, amostra de voz, configuração, saúde e diagnóstico."""
import json
import queue
import threading

from ...assistente import turno
from ...assistente.sessao import SESSAO
from ...nucleo.config import CFG, ESTADO, VOZES, config_publica, salvar_preferencias
from ...nucleo.eventos import EVENTOS
from ...nucleo.log import log
from ...voz.fala import AMOSTRA, Fala, com_nome, gravar_avisos_prontos
from ..servidor import Resposta, rota


@rota("GET", "/api/eventos")
def eventos(pedido):
    """Server-Sent Events: a tela fica ouvindo aqui (estado da esfera, respostas, avisos, painéis...)."""
    pedido.abrir("text/event-stream")
    q = EVENTOS.assinar()
    try:
        while True:
            try:
                dados = "data: " + json.dumps(q.get(timeout=15), ensure_ascii=False) + "\n\n"
            except queue.Empty:
                dados = ": ping\n\n"
            pedido.escrever(dados)
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        EVENTOS.sair(q)


@rota("GET", "/api/voz/{id_fala}")
def voz(pedido, id_fala):
    """O mp3 de uma fala, mandado conforme é gerado (a tela começa a tocar antes de terminar)."""
    fala = Fala.buscar(id_fala)
    if not fala:
        return 404, {}
    if fala.pronto and fala.erro:
        return 502, {}
    pedido.abrir("audio/mpeg", {"Content-Length": str(len(fala.pedacos))} if fala.pronto else None)
    try:
        for pedaco in fala.ler():
            pedido.escrever(pedaco)
    except (BrokenPipeError, ConnectionResetError):
        pass


@rota("GET", "/api/amostra/{voz}")
def amostra(pedido, voz):
    """Uma frase de exemplo na voz escolhida (engrenagem da tela). Fica guardada em .estado/amostras/."""
    if voz not in {v["id"] for v in VOZES} or not CFG["eleven_key"]:
        return 404, {}
    arquivo = ESTADO / "amostras" / f"{voz}-{CFG['velocidade_voz']}.mp3"
    if not arquivo.exists():
        dados = Fala(com_nome(AMOSTRA), voz=voz).esperar()
        if not dados:
            return 502, {}
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(dados)
    return Resposta(arquivo.read_bytes(), "audio/mpeg")


@rota("GET", "/api/config")
def ver_config(pedido):
    return config_publica()


@rota("POST", "/api/config")
def mudar_config(pedido):
    d = pedido.json()
    if d.get("voz") in {v["id"] for v in VOZES}:
        CFG["voz"] = d["voz"]
    if d.get("velocidade") is not None:
        CFG["velocidade_voz"] = round(min(1.2, max(0.7, float(d["velocidade"]))), 2)
    trocou_nome = False
    if isinstance(d.get("nome"), str) and d["nome"].strip():
        novo = " ".join(d["nome"].split())[:40]
        trocou_nome = novo != CFG["nome"]
        CFG["nome"] = novo
    for modo in ("modo_prova", "modo_texto"):
        if modo in d:
            CFG[modo] = bool(d[modo])
    salvar_preferencias()
    log({"evento": "config", "voz": CFG["voz"], "velocidade": CFG["velocidade_voz"]})
    threading.Thread(target=gravar_avisos_prontos, daemon=True).start()
    if trocou_nome:  # o nome vai na persona: precisa abrir o Claude de novo
        turno.reiniciar()
    return config_publica()


@rota("POST", "/api/reiniciar")
def reiniciar(pedido):
    turno.reiniciar()
    return {"ok": True}


@rota("GET", "/api/saude")
def saude(pedido):
    return {"claude": SESSAO.vivo(), "pasta": str(CFG["pasta"]), "modelo": CFG["modelo"], "telas": len(EVENTOS.ouvintes)}


@rota("POST", "/api/atalho")
def atalho(pedido):
    """O palmas.py avisa a tela: Ctrl+Alt+V gravando (e o volume da voz)."""
    try:
        d = pedido.json()
    except ValueError:
        d = {}
    evento = {"tipo": "atalho"}
    if d.get("estado") in ("ouvindo", "parado", "cancelado"):
        evento["estado"] = d["estado"]
    if d.get("nivel") is not None:
        evento["nivel"] = max(0.0, min(1.0, float(d["nivel"])))
    EVENTOS.emitir(evento)
    return {"ok": True}


@rota("POST", "/api/diag")
def diagnostico(pedido):
    """A tela avisa se a voz tocou ou falhou."""
    try:
        d = pedido.json()
    except ValueError:
        d = {}
    log({"evento": "tela", "tipo": str(d.get("evento", ""))[:40], "detalhe": str(d.get("detalhe", ""))[:300]})
    return {"ok": True}
