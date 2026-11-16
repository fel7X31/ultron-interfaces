import array
import io
import math
import random
import unittest
import wave

from ultron.voz.recorte import sem_silencio

TAXA = 16000


def wav_de(amostras):
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(array.array("h", amostras).tobytes())
    return saida.getvalue()


def duracao(wav):
    with wave.open(io.BytesIO(wav)) as arquivo:
        return arquivo.getnframes() / TAXA


def ruido(segundos, nivel=30):
    return [int(random.gauss(0, nivel)) for _ in range(int(segundos * TAXA))]


def voz(segundos, nivel=8000):
    return [int(nivel * math.sin(2 * math.pi * 220 * i / TAXA)) for i in range(int(segundos * TAXA))]


class TesteRecorte(unittest.TestCase):
    def test_tira_o_silencio_das_pontas_e_mantem_a_margem(self):
        cortado = sem_silencio(wav_de(ruido(2) + voz(1) + ruido(2)))
        self.assertAlmostEqual(duracao(cortado), 1.5, delta=0.1)

    def test_descarta_audio_so_com_ruido(self):
        self.assertIsNone(sem_silencio(wav_de(ruido(3))))

    def test_descarta_silencio_absoluto(self):
        self.assertIsNone(sem_silencio(wav_de([0] * TAXA)))

    def test_fala_com_pausa_no_meio_fica_inteira(self):
        cortado = sem_silencio(wav_de(ruido(1) + voz(1) + ruido(1) + voz(1) + ruido(1)))
        self.assertAlmostEqual(duracao(cortado), 3.5, delta=0.1)

    def test_audio_que_nao_e_wav_passa_direto(self):
        self.assertEqual(sem_silencio(b"webm qualquer"), b"webm qualquer")


if __name__ == "__main__":
    unittest.main()
