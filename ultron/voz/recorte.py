"""Tira o silêncio das pontas da fala e descarta áudio sem voz: é nesses trechos que a transcrição inventa frase."""
import array
import io
import math
import wave

JANELA_S = 0.03
MARGEM_S = 0.25                # folga pra não comer o começo e o fim da palavra
ACIMA_DO_FUNDO = 2             # com 3 já comia o fim da palavra nas falas mais fracas
PICO_MINIMO_DE_FALA = 4        # ruído constante fica perto de 2; a fala mais fraca medida no microfone do dono, em 12


def _ler_pcm(wav):
    with wave.open(io.BytesIO(wav)) as arquivo:
        if arquivo.getnchannels() != 1 or arquivo.getsampwidth() != 2:
            raise ValueError("só WAV mono de 16 bits")
        amostras = array.array("h")
        amostras.frombytes(arquivo.readframes(arquivo.getnframes()))
        return arquivo.getframerate(), amostras


def _escrever_pcm(taxa, amostras):
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        arquivo.writeframes(amostras.tobytes())
    return saida.getvalue()


def _energias(amostras, tamanho):
    return [math.sqrt(sum(a * a for a in amostras[i:i + tamanho]) / tamanho)
            for i in range(0, len(amostras) - tamanho + 1, tamanho)]


def _trecho_falado(energias, fundo):
    """Primeira e última janela (fim exclusivo) com fala, já com a margem."""
    falando = [i for i, energia in enumerate(energias) if energia > fundo * ACIMA_DO_FUNDO]
    margem = int(MARGEM_S / JANELA_S)
    return max(0, falando[0] - margem), min(len(energias), falando[-1] + 1 + margem)


def sem_silencio(wav):
    """O WAV só com o trecho falado, None se não tem voz, ou o próprio áudio se não for um WAV que dê pra ler."""
    try:
        taxa, amostras = _ler_pcm(wav)
    except (wave.Error, EOFError, ValueError):
        return wav
    tamanho = int(taxa * JANELA_S)
    energias = _energias(amostras, tamanho)
    if not energias:
        return wav
    fundo = sorted(energias)[len(energias) // 10]
    if max(energias) < PICO_MINIMO_DE_FALA * max(fundo, 1):
        return None
    inicio, fim = _trecho_falado(energias, fundo)
    return _escrever_pcm(taxa, amostras[inicio * tamanho:fim * tamanho])
