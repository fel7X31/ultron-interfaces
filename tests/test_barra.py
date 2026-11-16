"""A barra do topo: quando aparece, o tema e as rotas que ela usa."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from ultron.http.rotas import sistema
from ultron.http.servidor import criar_servidor
from ultron.nucleo.config import CFG
from ultron.nucleo.eventos import EVENTOS
from ultron.recursos import barra


class TesteQuandoAparece(unittest.TestCase):
    def setUp(self):
        self.antes = barra.TELA["visivel"]

    def tearDown(self):
        barra.TELA["visivel"] = self.antes

    def test_aparece_sem_tela_ou_com_a_tela_minimizada(self):
        ouvinte_da_barra = EVENTOS.assinar(tela=False)
        try:
            self.assertTrue(barra.mostrar())  # só a barra ouvindo: nenhuma tela aberta
            tela = EVENTOS.assinar()
            barra.tela_mudou(True)
            self.assertFalse(barra.mostrar())
            barra.tela_mudou(False)
            self.assertTrue(barra.mostrar())
            barra.tela_mudou(True)
            EVENTOS.sair(tela)
            self.assertTrue(barra.mostrar())  # a tela fechou
        finally:
            EVENTOS.sair(ouvinte_da_barra)

    def test_a_barra_nao_conta_como_tela(self):
        antes = EVENTOS.telas()
        ouvinte = EVENTOS.assinar(tela=False)
        self.assertEqual(EVENTOS.telas(), antes)
        EVENTOS.sair(ouvinte)


class TesteRotasDaBarra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = criar_servidor(0)
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()

    def pegar(self, caminho, corpo=None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + caminho, data=dados), timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read() or b"{}")

    def test_barra_e_ias(self):
        codigo, dados = self.pegar("/api/barra")
        self.assertEqual(codigo, 200)
        self.assertIn(dados["tema"], ("prata", "escuro"))
        self.assertIn("mostrar", dados)
        codigo, dados = self.pegar("/api/ias")
        self.assertEqual(codigo, 200)
        self.assertTrue(any(o["ia"] == "gemini" for o in dados["opcoes"]))

    def test_tema_avisa_a_barra(self):
        antes = CFG["tema"]
        ouvinte = EVENTOS.assinar(tela=False)
        try:
            with mock.patch.object(sistema, "salvar_preferencias"):
                outro = "escuro" if antes == "prata" else "prata"
                self.assertEqual(self.pegar("/api/tema", {"tema": outro})[0], 200)
                self.assertEqual(self.pegar("/api/tema", {"tema": "rosa"})[0], 400)
            eventos = [ouvinte.get(timeout=2) for _ in range(2)]
            self.assertIn({"tipo": "tema", "tema": outro}, eventos)
        finally:
            CFG["tema"] = antes
            EVENTOS.sair(ouvinte)

    def test_acao_do_pc_desconhecida_vira_400(self):
        self.assertEqual(self.pegar("/api/pc/acao", {"acao": "explodir"})[0], 400)


if __name__ == "__main__":
    unittest.main()
