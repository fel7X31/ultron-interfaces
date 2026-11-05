"""Comandos de voz que não passam pelo Claude e a confirmação da trava."""
import unittest
from unittest import mock

from ultron.assistente import comandos
from ultron.assistente.confirmacao import autorizou_no_pedido, eh_confirmacao, pediu_confirmacao
from ultron.nucleo.config import CFG


def tentar(texto, aguardando=False):
    registro = {}
    return comandos.tentar(comandos.Fala(texto, aguardando, registro)), registro


class TesteComandos(unittest.TestCase):
    def test_controle_de_musica(self):
        self.assertEqual(tentar("Próxima música!")[0], "Próxima.")
        self.assertEqual(tentar("pausa a música")[0], "Pausei.")

    def test_curriculo(self):
        self.assertIn("análise", tentar("quero analisar meu currículo")[0])
        self.assertIn("fechado", tentar("fecha o currículo")[0])

    def test_pergunta_normal_vai_pro_claude(self):
        self.assertIsNone(tentar("qual é a minha agenda de amanhã?")[0])
        self.assertIsNone(tentar("me explica como funciona uma API REST com exemplos")[0])

    def test_modo_prova(self):
        antes = CFG["modo_prova"]
        try:
            with mock.patch.object(comandos, "salvar_preferencias"):
                self.assertIn("ativado", tentar("ativa o modo prova")[0])
                self.assertTrue(CFG["modo_prova"])
                self.assertEqual(tentar("ok")[0], comandos.SILENCIO)      # concordou: fica quieto
                self.assertIsNone(tentar("ok", aguardando=True)[0])       # mas "ok" ao "Confirma?" vai pro Claude
                self.assertIn("encerrado", tentar("desliga o modo prova")[0])
        finally:
            CFG["modo_prova"] = antes


class TesteConfirmacao(unittest.TestCase):
    def test_sim(self):
        for frase in ("sim", "pode", "Ultron, pode fazer", "eu confirmo", "confirmado"):
            self.assertTrue(eh_confirmacao(frase), frase)

    def test_nao(self):
        for frase in ("não", "espera", "qual é o clima hoje", "pode não"):
            self.assertFalse(eh_confirmacao(frase), frase)

    def test_permissao_no_pedido(self):
        self.assertTrue(autorizou_no_pedido("cria o arquivo, pode fazer sem perguntar"))
        self.assertFalse(autorizou_no_pedido("não pode apagar nada"))

    def test_pediu_confirmacao(self):
        self.assertTrue(pediu_confirmacao("Vou apagar o arquivo x. Confirma?"))
        self.assertFalse(pediu_confirmacao("Feito."))


if __name__ == "__main__":
    unittest.main()
