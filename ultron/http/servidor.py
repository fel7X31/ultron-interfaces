"""Servidor web mínimo (só biblioteca padrão) com roteador por decorador.

Uma rota é uma função registrada com @rota("GET", "/api/caminho"). Pedaço entre chaves vira parâmetro:
@rota("GET", "/api/voz/{id_fala}") chama a função com id_fala="...". Caminho fixo ganha de caminho com chaves.

A função recebe o Pedido (e os parâmetros) e devolve:
    dict ou list          -> JSON 200
    (codigo, dict)        -> JSON com esse código
    Resposta(...)         -> bytes com o tipo que você quiser (pdf, mp3, docx...)
    None                  -> a própria função já escreveu a resposta (eventos ao vivo, áudio aos pedaços)
ValueError vira 400 com a mensagem; outro erro vira 500 e vai pro log.
"""
import json
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..nucleo.config import WEB
from ..nucleo.log import log_erro

TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
ROTAS = {}       # (método, caminho) -> função        caminhos fixos
ROTAS_PARAM = []  # (método, regex, função)           caminhos com {parametro}


def rota(metodo, caminho):
    def registrar(funcao):
        if "{" in caminho:
            regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", caminho) + "$")
            ROTAS_PARAM.append((metodo, regex, funcao))
        else:
            ROTAS[(metodo, caminho)] = funcao
        return funcao
    return registrar


def achar_rota(metodo, caminho):
    if (metodo, caminho) in ROTAS:
        return ROTAS[(metodo, caminho)], {}
    for m, regex, funcao in ROTAS_PARAM:
        achou = regex.match(caminho) if m == metodo else None
        if achou:
            return funcao, achou.groupdict()
    return None, {}


class Resposta:
    def __init__(self, corpo=b"", tipo="application/json", codigo=200, cabecalhos=None):
        self.corpo, self.tipo, self.codigo, self.cabecalhos = corpo, tipo, codigo, cabecalhos or {}


def em_json(dados, codigo=200):
    return Resposta(json.dumps(dados, ensure_ascii=False).encode(), codigo=codigo)


class Pedido:
    """O pedido que chegou, com atalhos pra ler e pra responder aos pedaços."""

    def __init__(self, handler, metodo):
        self.handler = handler
        partes = urllib.parse.urlsplit(handler.path)
        self.caminho = partes.path
        self.consulta = urllib.parse.parse_qs(partes.query, keep_blank_values=True)
        tamanho = int(handler.headers.get("Content-Length", "0") or 0) if metodo == "POST" else 0
        self.corpo = handler.rfile.read(tamanho) if tamanho else b""

    def param(self, nome, padrao=""):
        """?nome=valor da URL."""
        return self.consulta.get(nome, [padrao])[0]

    def tem_param(self, nome):
        return nome in self.consulta

    def json(self):
        """Corpo JSON (ou {} se veio vazio). JSON quebrado vira ValueError -> 400."""
        return json.loads(self.corpo or b"{}")

    def cabecalho(self, nome, padrao=""):
        return self.handler.headers.get(nome, padrao)

    def abrir(self, tipo, cabecalhos=None):
        """Começa uma resposta aos pedaços (eventos ao vivo, áudio, texto sendo escrito)."""
        h = self.handler
        h.send_response(200)
        h.send_header("Content-Type", tipo)
        h.send_header("Cache-Control", "no-store")
        for k, v in (cabecalhos or {}).items():
            h.send_header(k, v)
        h.end_headers()

    def escrever(self, dados):
        self.handler.wfile.write(dados if isinstance(dados, bytes) else dados.encode("utf-8"))
        self.handler.wfile.flush()


class Tratador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")

    def _atender(self, metodo):
        pedido = Pedido(self, metodo)
        funcao, params = achar_rota(metodo, pedido.caminho)
        if not funcao:
            resultado = arquivo_da_tela(pedido.caminho) if metodo == "GET" else em_json({}, 404)
        else:
            try:
                resultado = funcao(pedido, **params)
            except (BrokenPipeError, ConnectionResetError):
                return
            except ValueError as erro:
                resultado = em_json({"erro": str(erro)[:300]}, 400)
            except Exception as erro:
                log_erro("rota_falhou", erro, rota=pedido.caminho)
                resultado = em_json({"erro": "Deu erro: " + str(erro)[:300]}, 500)
        if resultado is None:
            return
        if isinstance(resultado, tuple):
            resultado = em_json(resultado[1], resultado[0])
        elif not isinstance(resultado, Resposta):
            resultado = em_json(resultado)
        self._enviar(resultado)

    def _enviar(self, r):
        try:
            self.send_response(r.codigo)
            self.send_header("Content-Type", r.tipo)
            self.send_header("Content-Length", str(len(r.corpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in r.cabecalhos.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(r.corpo)
        except (BrokenPipeError, ConnectionResetError):
            pass


def arquivo_da_tela(caminho):
    """Arquivos de web/ (/, /chat.html, /curriculo.html...). Nada fora dessa pasta."""
    raiz = WEB.resolve()
    arquivo = (WEB / ("index.html" if caminho == "/" else urllib.parse.unquote(caminho).lstrip("/"))).resolve()
    if raiz not in arquivo.parents or not arquivo.is_file():
        return em_json({}, 404)
    return Resposta(arquivo.read_bytes(), TIPOS.get(arquivo.suffix, "application/octet-stream"))


def criar_servidor(porta):
    from . import rotas  # noqa: F401  (importar registra todas as rotas)
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Tratador)
    servidor.daemon_threads = True
    return servidor
