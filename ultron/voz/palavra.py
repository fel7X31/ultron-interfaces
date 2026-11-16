"""Reconhece a palavra "Ultron" comparando cada som curto com gravações da sua própria voz.

O som vira uma sequência de coeficientes (MFCC) e é alinhado com as gravações (DTW): quanto menor a distância,
mais parecido. Só precisa de numpy: roda na CPU, sem internet e sem modelo baixado.
"""
import collections
import functools

import numpy as np

TAXA = 16000
JANELA = 400  # 25 ms
PASSO = 160  # 10 ms
N_FFT = 512
N_FILTROS = 26
N_COEFICIENTES = 12
PRE_ENFASE = 0.97

NIVEL_MIN = 0.003  # volume abaixo disso nunca é fala
RAZAO_FUNDO = 4.0  # a fala precisa estar esse tanto acima do ruído do ambiente
DURACAO_MIN = 0.3  # palma e estalo são mais curtos que isso
DURACAO_MAX = 1.4  # frase é mais longa que isso
PAUSA_FIM = 0.2  # silêncio que encerra a palavra
BLOCOS_ANTES = 8  # blocos guardados de antes do som começar (o começo da palavra é fraco)

MELHORES = 3  # compara com a média das gravações mais parecidas
MARGEM = 1.15  # sobre a maior distância entre as suas gravações: aumente se ele não te ouvir, diminua se ligar sozinho


@functools.lru_cache(maxsize=1)
def _filtros_mel():
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    hertz = lambda m: 700 * (10 ** (m / 2595) - 1)
    pontos = hertz(np.linspace(mel(80), mel(TAXA / 2), N_FILTROS + 2))
    posicoes = np.floor((N_FFT + 1) * pontos / TAXA).astype(int)
    filtros = np.zeros((N_FILTROS, N_FFT // 2 + 1))
    for i, (a, b, c) in enumerate(zip(posicoes, posicoes[1:], posicoes[2:])):
        filtros[i, a:b] = (np.arange(a, b) - a) / max(b - a, 1)
        filtros[i, b:c] = (c - np.arange(b, c)) / max(c - b, 1)
    return filtros


@functools.lru_cache(maxsize=1)
def _matriz_dct():
    k = np.arange(1, N_COEFICIENTES + 1)[:, None]
    return np.cos(np.pi * k * (2 * np.arange(N_FILTROS) + 1) / (2 * N_FILTROS))


def _reamostrar(audio, taxa):
    if taxa == TAXA:
        return audio
    n = int(len(audio) * TAXA / taxa)
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)


def coeficientes(audio, taxa):
    """Uma linha de coeficientes por janela de 25 ms, sem depender do volume nem do microfone."""
    audio = _reamostrar(np.asarray(audio, dtype=float), taxa)
    audio = np.append(audio[0], audio[1:] - PRE_ENFASE * audio[:-1])
    janelas = np.lib.stride_tricks.sliding_window_view(audio, JANELA)[::PASSO] * np.hamming(JANELA)
    potencia = np.abs(np.fft.rfft(janelas, N_FFT)) ** 2
    energias = np.log(potencia @ _filtros_mel().T + 1e-10)
    saida = energias @ _matriz_dct().T
    return (saida - saida.mean(axis=0)) / (saida.std(axis=0) + 1e-10)


def _alinhar(a, b):
    """Custo do melhor alinhamento entre duas sequências (DTW), dividido pelo tamanho delas."""
    custo = np.linalg.norm(a[:, None] - b[None, :], axis=2)
    linha = np.cumsum(custo[0])
    for i in range(1, len(a)):
        anterior, linha = linha, np.empty(len(b))
        linha[0] = anterior[0] + custo[i, 0]
        for j in range(1, len(b)):
            linha[j] = custo[i, j] + min(anterior[j], linha[j - 1], anterior[j - 1])
    return float(linha[-1]) / (len(a) + len(b))


def distancia(coefs, modelos):
    """O quanto o som difere das gravações (média das mais parecidas)."""
    return float(np.mean(sorted(_alinhar(coefs, m) for m in modelos)[:MELHORES]))


def treinar(trechos, taxa):
    """(modelos, limite). O limite vem de quanto as suas próprias gravações diferem entre si."""
    modelos = [coeficientes(t, taxa) for t in trechos]
    diferencas = [distancia(m, modelos[:i] + modelos[i + 1:]) for i, m in enumerate(modelos)]
    return modelos, max(diferencas) * MARGEM


def salvar(arquivo, modelos, limite):
    np.savez(arquivo, limite=limite, **{f"m{i}": m for i, m in enumerate(modelos)})


def carregar(arquivo):
    """(modelos, limite), ou None se você ainda não gravou a sua voz."""
    try:
        with np.load(arquivo) as dados:
            return [dados[k] for k in dados.files if k != "limite"], float(dados["limite"])
    except (OSError, ValueError, KeyError):
        return None


class Segmentador:
    """Recebe o microfone aos poucos e entrega cada som isolado que tem o tamanho de uma palavra."""

    def __init__(self, taxa):
        self.taxa = taxa
        self.fundo = 0.001
        self.antes = collections.deque(maxlen=BLOCOS_ANTES)
        self.pedacos = []
        self.silencio = 0.0
        self.descartando = False

    def receber(self, bloco):
        """O áudio da palavra quando ela termina; None no resto do tempo."""
        nivel = float(np.sqrt(np.mean((bloco - bloco.mean()) ** 2)))
        falando = nivel > max(NIVEL_MIN, self.fundo * RAZAO_FUNDO)
        duracao = len(bloco) / self.taxa
        if self.descartando:
            return self._esperar_acabar(falando, nivel, duracao)
        if not self.pedacos:
            self._esperar_comecar(bloco, falando, nivel)
            return None
        self.pedacos.append(bloco)
        self.silencio = 0.0 if falando else self.silencio + duracao
        if self.silencio >= PAUSA_FIM:
            return self._fechar()
        if self._tamanho() > DURACAO_MAX + PAUSA_FIM:
            self.pedacos, self.descartando = [], True
        return None

    def _esperar_comecar(self, bloco, falando, nivel):
        if falando:
            self.pedacos = [*self.antes, bloco]
            self.silencio = 0.0
            self.antes.clear()
        else:
            self.fundo = 0.98 * self.fundo + 0.02 * nivel
            self.antes.append(bloco)

    def _esperar_acabar(self, falando, nivel, duracao):
        """Som longo demais: ignora até parar. O fundo sobe devagar pra um ruído novo (ventilador) não travar aqui."""
        self.fundo = 0.995 * self.fundo + 0.005 * nivel
        self.silencio = 0.0 if falando else self.silencio + duracao
        if self.silencio >= PAUSA_FIM:
            self.descartando = False
        return None

    def _tamanho(self):
        return sum(len(p) for p in self.pedacos) / self.taxa

    def _fechar(self):
        audio = np.concatenate(self.pedacos)[:-int(self.silencio * self.taxa) or None]
        self.pedacos = []
        return audio if DURACAO_MIN <= len(audio) / self.taxa <= DURACAO_MAX else None
