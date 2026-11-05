"""Áudio -> texto: whisper local (grátis) e, se ele não responder, ElevenLabs Scribe."""
import json
import re
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path

from ..nucleo.config import CFG
from ..nucleo.log import log
from ..nucleo.texto import normalizar

# Frases que o whisper "inventa" quando o áudio é quase só silêncio (vêm de legendas de vídeo).
ALUCINACOES = [re.compile(p) for p in (
    r"^legendas? (por|pela|de)\b", r"\bruberti\b", r"\bamara org\b", r"\bobrigad[oa] por assistir", r"\binscreva se\b",
)]


def multipart(campos, nome_arquivo, conteudo, mime, campo_arquivo="file"):
    limite = uuid.uuid4().hex
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in campos.items()]
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo_arquivo}"; filename="{nome_arquivo}"\r\n'
                  f"Content-Type: {mime}\r\n\r\n".encode() + conteudo + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def para_wav(audio, mime):
    ext = ".mp4" if "mp4" in mime else ".ogg" if "ogg" in mime else ".webm"
    with tempfile.TemporaryDirectory() as tmp:
        entrada, saida = Path(tmp) / ("fala" + ext), Path(tmp) / "fala.wav"
        entrada.write_bytes(audio)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(entrada), "-ar", "16000", "-ac", "1", str(saida)],
                       check=True)
        return saida.read_bytes()


def transcrever_whisper(audio, mime):
    corpo, tipo = multipart({"response_format": "json", "temperature": "0.0"}, "fala.wav", para_wav(audio, mime), "audio/wav")
    req = urllib.request.Request(CFG["whisper_url"] + "/inference", data=corpo, headers={"Content-Type": tipo})
    with urllib.request.urlopen(req, timeout=25) as r:  # passou disso, usa o ElevenLabs
        return json.loads(r.read().decode("utf-8")).get("text", "")


def transcrever_scribe(audio, mime):
    corpo, tipo = multipart({"model_id": "scribe_v1", "language_code": "por", "keyterms": "Ultron"}, "fala.webm", audio, mime)
    req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=corpo,
                                 headers={"Content-Type": tipo, "xi-api-key": CFG["eleven_key"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8")).get("text", "")


def transcrever(audio, mime):
    """Texto do que foi falado, ou "" se era só silêncio/ruído."""
    modo = CFG["transcricao"]
    if modo in ("auto", "whisper"):
        try:
            texto = transcrever_whisper(audio, mime)
        except Exception as erro:  # whisper fora do ar
            if modo == "whisper":
                raise
            log({"evento": "whisper_falhou", "erro": str(erro)})
            texto = transcrever_scribe(audio, mime)
    else:
        texto = transcrever_scribe(audio, mime)
    texto = " ".join(re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", texto).split())  # [BLANK_AUDIO], (música)
    limpo = " ".join(normalizar(texto))
    if len(limpo.replace(" ", "")) < 2 or any(p.search(limpo) for p in ALUCINACOES):  # "ok" confirma a trava
        log({"evento": "transcricao_descartada", "texto": texto})
        return ""
    return texto
