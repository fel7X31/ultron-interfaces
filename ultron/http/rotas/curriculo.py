"""Tela do currículo (web/curriculo.html): arquivo, edição, estilo, exportar e a conversa com o Claude."""
import json
import urllib.parse

from ...nucleo.log import log_erro
from ...recursos import curriculo
from ..servidor import Resposta, rota

TIPOS_EXPORTAR = {"pdf": "application/pdf",
                  "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@rota("GET", "/api/curriculo/estado")
def estado(pedido):
    return curriculo.estado_publico()


@rota("GET", "/api/curriculo/original")
def original(pedido):
    p = curriculo.caminho_original()
    if not p:
        return 404, {}
    return Resposta(p.read_bytes(), "application/pdf" if p.suffix == ".pdf" else "application/octet-stream")


@rota("POST", "/api/curriculo/arquivo")
def receber_arquivo(pedido):
    nome = urllib.parse.unquote(pedido.cabecalho("X-Nome", "curriculo"))
    return curriculo.receber_arquivo(nome, pedido.corpo)


@rota("POST", "/api/curriculo/editar")
def editar(pedido):
    d = pedido.json()
    curriculo.guardar_edicao(str(d.get("modo", "")), d.get("curriculo", ""), d.get("html"))
    return {"ok": True}


@rota("POST", "/api/curriculo/recomecar")
def recomecar(pedido):
    return curriculo.recomecar(str(pedido.json().get("modo", "")))


@rota("POST", "/api/curriculo/estilo")
def estilo(pedido):
    d = pedido.json()
    return curriculo.salvar_estilo(str(d.get("modo", "")), d.get("estilo") or {})


@rota("POST", "/api/curriculo/fechar-arquivo")
def fechar_arquivo(pedido):
    return curriculo.fechar_arquivo()


@rota("POST", "/api/curriculo/exportar")
def exportar(pedido):
    d = pedido.json()
    formato = "pdf" if d.get("formato") == "pdf" else "docx"
    nome, dados = curriculo.exportar(formato, str(d.get("curriculo", "")), d.get("estilo"), d.get("html"))
    return Resposta(dados, TIPOS_EXPORTAR[formato], cabecalhos={"X-Nome": urllib.parse.quote(nome)})


@rota("POST", "/api/curriculo/conversar")
def conversar(pedido):
    """Resposta aos poucos (uma linha JSON por pedaço): a tela mostra o Claude escrevendo."""
    d = pedido.json()
    pedido.abrir("application/x-ndjson; charset=utf-8")

    def escrever(ev):
        pedido.escrever(json.dumps(ev, ensure_ascii=False) + "\n")

    try:
        curriculo.conversar(str(d.get("modo", "")), str(d.get("mensagem", ""))[:6000],
                            d.get("curriculo"), escrever, d.get("html"))
    except (BrokenPipeError, ConnectionResetError):
        pass
    except Exception as erro:
        log_erro("curriculo_falhou", erro)
        try:
            escrever({"t": "erro", "erro": str(erro)[:300]})
        except OSError:
            pass
