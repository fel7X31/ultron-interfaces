"""Texto -> voz (ElevenLabs ou Fish Audio). Gera uma vez e entrega aos pedaços pra quem pedir (/api/voz/<id>)."""
import json
import threading
import time
import urllib.error
import urllib.request
import uuid

from ..nucleo.config import CFG, VOZES, voz_ligada
from ..nucleo.log import log

# Ditas quando ele vai trabalhar e não escreveu o próprio aviso.
AVISOS_PRONTOS = ["Um instante, {nome}. Isso é rápido pra mim.", "Já estou nisso, {nome}.",
                  "Verificando, {nome}. Sem pressa.", "Consultando, {nome}. Previsível como sempre.",
                  "Deixe comigo, {nome}."]
AMOSTRA = "{nome}. É assim que eu vou falar daqui pra frente. Acostume-se."


def com_nome(frase):
    return frase.replace("{nome}", CFG["nome"])


class Fala:
    todas = {}   # falas do dia a dia (guarda as últimas 20)
    fixas = {}   # frases prontas, geradas uma vez quando abre

    def __init__(self, texto, voz=None, velocidade=None):
        self.pedacos = bytearray()
        self.pronto = False
        self.erro = None
        self.cond = threading.Condition()
        self.voz = voz or CFG["voz"]
        self.velocidade = velocidade if velocidade is not None else CFG["velocidade_voz"]
        threading.Thread(target=self._gerar, args=(texto,), daemon=True).start()

    def esperar(self, limite=60):
        with self.cond:
            fim = time.time() + limite
            while not self.pronto and time.time() < fim:
                self.cond.wait(timeout=1)
        return bytes(self.pedacos) if self.pronto and not self.erro else b""

    def _pedido(self, texto):
        provedor = next((v.get("provedor") for v in VOZES if v.get("id") == self.voz), None)
        if provedor == "fish":
            tom = CFG["fish_tom"] + " " if CFG["fish_tom"] else ""
            corpo = {"text": tom + texto, "reference_id": self.voz, "format": "mp3", "mp3_bitrate": 128,
                     "latency": "balanced", "normalize": True}
            if self.velocidade != 1.0:
                corpo["prosody"] = {"speed": self.velocidade}
            return urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(corpo).encode(), headers={
                "Authorization": f"Bearer {CFG['fish_key']}", "Content-Type": "application/json", "model": CFG["fish_modelo"]})
        corpo = {"text": texto, "model_id": CFG["modelo_voz"]}
        if self.velocidade != 1.0:
            corpo["voice_settings"] = {"speed": self.velocidade}
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voz}/stream?output_format=mp3_44100_128"
        return urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                      headers={"xi-api-key": CFG["eleven_key"], "Content-Type": "application/json"})

    def _gerar(self, texto):
        try:
            with urllib.request.urlopen(self._pedido(texto), timeout=60) as r:
                while True:
                    pedaco = r.read(4096)
                    if not pedaco:
                        break
                    with self.cond:
                        self.pedacos.extend(pedaco)
                        self.cond.notify_all()
        except urllib.error.HTTPError as erro:
            self.erro = erro.code
            log({"evento": "voz_falhou", "codigo": erro.code, "detalhe": erro.read()[:300].decode("utf-8", "ignore")})
        except Exception as erro:
            self.erro = repr(erro)
            log({"evento": "voz_falhou", "detalhe": repr(erro)})
        finally:
            with self.cond:
                self.pronto = True
                self.cond.notify_all()

    def ler(self):
        """Os bytes do mp3 conforme vão chegando (a tela começa a tocar antes de a voz terminar de gerar)."""
        pos = 0
        while True:
            with self.cond:
                while pos >= len(self.pedacos) and not self.pronto:
                    self.cond.wait(timeout=30)
                novo = bytes(self.pedacos[pos:])
                acabou = self.pronto
            pos += len(novo)
            if novo:
                yield novo
            if acabou and pos >= len(self.pedacos):
                return

    @classmethod
    def fixa(cls, texto):
        chave = f"{CFG['voz']}|{CFG['velocidade_voz']}|{texto}"
        id_fala = "f" + uuid.uuid5(uuid.NAMESPACE_URL, chave).hex[:11]
        if id_fala not in cls.fixas:
            cls.fixas[id_fala] = cls(texto)
        return id_fala

    @classmethod
    def criar(cls, texto):
        id_fala = uuid.uuid4().hex[:12]
        cls.todas[id_fala] = cls(texto)
        for antigo in list(cls.todas)[:-20]:
            cls.todas.pop(antigo, None)
        return id_fala

    @classmethod
    def buscar(cls, id_fala):
        return cls.todas.get(id_fala) or cls.fixas.get(id_fala)


def url_fala(texto, fixa=False):
    """Endereço do áudio pra tela tocar, ou "" quando a voz está desligada."""
    if not voz_ligada() or not texto:
        return ""
    return f"/api/voz/{Fala.fixa(texto) if fixa else Fala.criar(texto)}"


def gravar_avisos_prontos():
    """Deixa as frases prontas ("Um instante...") gravadas na voz escolhida."""
    if CFG["eleven_key"]:
        for frase in AVISOS_PRONTOS:
            Fala.fixa(com_nome(frase))
