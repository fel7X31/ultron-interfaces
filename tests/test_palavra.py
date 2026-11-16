"""Reconhecimento da palavra: separação dos sons e comparação com as gravações."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ultron.voz import palavra

TAXA = 16000
BLOCO = 160


def silencio(segundos):
    return np.random.default_rng(1).normal(0, 0.0003, int(segundos * TAXA))


def varredura(inicio, fim, segundos=0.6):
    """Um som que muda de frequência ao longo do tempo, como uma palavra."""
    t = np.arange(int(segundos * TAXA)) / TAXA
    return 0.3 * np.sin(2 * np.pi * (inicio + (fim - inicio) * t / segundos / 2) * t)


def segmentos(audio):
    seg = palavra.Segmentador(TAXA)
    achados = (seg.receber(audio[i:i + BLOCO]) for i in range(0, len(audio) - BLOCO + 1, BLOCO))
    return [a for a in achados if a is not None]


class TestSegmentador(unittest.TestCase):
    def test_entrega_um_som_do_tamanho_de_uma_palavra(self):
        achados = segmentos(np.concatenate([silencio(1), varredura(300, 1500), silencio(1)]))
        self.assertEqual(len(achados), 1)
        self.assertAlmostEqual(len(achados[0]) / TAXA, 0.68, delta=0.1)

    def test_ignora_palma(self):
        self.assertEqual(segmentos(np.concatenate([silencio(1), varredura(300, 1500, 0.08), silencio(1)])), [])

    def test_ignora_som_longo_e_volta_a_ouvir(self):
        audio = np.concatenate([silencio(1), varredura(300, 1500, 3), silencio(1), varredura(300, 1500), silencio(1)])
        self.assertEqual(len(segmentos(audio)), 1)


class TestComparacao(unittest.TestCase):
    def setUp(self):
        duracoes = (0.5, 0.55, 0.6, 0.65, 0.7)
        self.modelos, self.limite = palavra.treinar([varredura(300, 2500, d) for d in duracoes], TAXA)

    def distancia(self, audio):
        return palavra.distancia(palavra.coeficientes(audio, TAXA), self.modelos)

    def test_reconhece_o_mesmo_som_mais_devagar(self):
        self.assertLessEqual(self.distancia(varredura(300, 2500, 0.62)), self.limite)

    def test_recusa_som_diferente(self):
        self.assertGreater(self.distancia(varredura(3500, 400, 0.6)), self.limite)

    def test_volume_nao_importa(self):
        audio = varredura(300, 2500, 0.62)
        self.assertAlmostEqual(self.distancia(audio), self.distancia(audio * 0.1), places=3)

    def test_salva_e_carrega(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "voz.npz"
            palavra.salvar(arquivo, self.modelos, self.limite)
            modelos, limite = palavra.carregar(arquivo)
        self.assertEqual(len(modelos), len(self.modelos))
        self.assertEqual(limite, self.limite)

    def test_sem_gravacao_devolve_none(self):
        self.assertIsNone(palavra.carregar(Path(tempfile.gettempdir()) / "nao-existe-ultron.npz"))


if __name__ == "__main__":
    unittest.main()
