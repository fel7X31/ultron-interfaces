"""Chamar o Ultron pelo nome: a leitura do que o chamado.ps1 escreve e o fim da fala depois do bipe."""
import unittest

from ultron.voz.chamado import Chamado, FimDaFala


class TesteChamado(unittest.TestCase):
    def test_le_as_linhas_do_script(self):
        ouviu, avisos = [], []
        chamado = Chamado(lambda *a: ouviu.append(a), avisos.append)
        chamado.tratar("pronto\n")
        chamado.tratar("ultron High 0.91 0.62\n")
        chamado.tratar("erro sem microfone\n")
        self.assertEqual(ouviu, [("High", 0.91, 0.62)])
        self.assertEqual(len(avisos), 2)
        self.assertIn("sem microfone", avisos[1])


def passar(fim, volumes, bloco=0.05):
    situacao = None
    for v in volumes:
        situacao = fim.receber(v, bloco)
        if situacao in ("acabou", "nada"):
            break
    return situacao


class TesteFimDaFala(unittest.TestCase):
    def test_acaba_depois_de_falar_e_ficar_quieto(self):
        fundo, voz = [0.0004] * 10, [0.004] * 20
        self.assertEqual(passar(FimDaFala(5, 1.0), fundo + voz + [0.0005] * 30), "acabou")

    def test_continua_enquanto_fala_com_pausas_curtas(self):
        falas = [0.0004] * 10 + ([0.004] * 10 + [0.0005] * 8) * 4
        self.assertEqual(passar(FimDaFala(5, 1.0), falas), "falando")

    def test_nada_se_nao_falou(self):
        self.assertEqual(passar(FimDaFala(2, 1.0), [0.0004] * 60), "nada")

    def test_estalo_nao_e_fala(self):
        self.assertEqual(passar(FimDaFala(2, 1.0), [0.0004] * 10 + [0.01] * 2 + [0.0004] * 60), "nada")

    def test_microfone_alto(self):
        self.assertEqual(passar(FimDaFala(5, 1.0), [0.02] * 10 + [0.2] * 20 + [0.02] * 30), "acabou")
