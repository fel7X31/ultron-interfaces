"""Comandos de voz que não passam pelo Claude e a confirmação da trava."""
import unittest
from unittest import mock

from ultron.assistente import comandos
from ultron.assistente.confirmacao import autorizou_no_pedido, eh_confirmacao, pediu_confirmacao
from ultron.nucleo.config import CFG
from ultron.nucleo.texto import limpar_para_fala
from ultron.voz import fala, transcricao


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

    def test_modo_entrevista_troca_o_idioma_e_segue_pro_claude(self):
        try:
            self.assertIsNone(tentar("modo entrevista")[0])
            self.assertTrue(transcricao.IDIOMA["livre"])
            self.assertNotIn("language_code", transcricao._campos_scribe())
            self.assertIsNone(tentar("terminei o código")[0])
            self.assertTrue(transcricao.IDIOMA["livre"])
            self.assertIsNone(tentar("terminar")[0])
            self.assertFalse(transcricao.IDIOMA["livre"])
            self.assertEqual(transcricao._campos_scribe()["language_code"], "por")
        finally:
            transcricao.liberar_idioma(False)

    def test_entende_o_modo_entrevista_mal_transcrito(self):
        for frase in ("Modo entre vídeos", "Modo entrevistador", "Modo do Entrevista", "Módulo Entrevistas", "interview mode"):
            with self.subTest(frase):
                try:
                    tentar(frase)
                    self.assertTrue(transcricao.IDIOMA["livre"])
                finally:
                    transcricao.liberar_idioma(False)

    def test_entrevista_usa_voz_em_ingles_e_termos_proprios(self):
        self.assertEqual(fala.voz_do_momento(), {})
        try:
            transcricao.liberar_idioma(True)
            self.assertEqual(fala.voz_do_momento(), fala.ENTREVISTA)
            self.assertIn("Pulumi", transcricao._campos_scribe()["keyterms"])
        finally:
            transcricao.liberar_idioma(False)

    def test_fala_longa_termina_em_frase_inteira(self):
        frase = "Uma frase completa. " * 200
        cortada = limpar_para_fala(frase)
        self.assertLessEqual(len(cortada), 2500)
        self.assertGreater(len(cortada), 2400)
        self.assertTrue(cortada.endswith("."))

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
