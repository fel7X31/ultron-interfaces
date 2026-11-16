"""A memória do Ultron (memoria.md na pasta dele), o grafo e os comandos de voz "lembra que..." / "esquece que..."."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from ultron.assistente import comandos
from ultron.http.servidor import criar_servidor
from ultron.nucleo.config import CFG
from ultron.recursos import memoria


def tentar(texto):
    return comandos.tentar(comandos.Fala(texto, False, {}))


class ComPastaTemporaria(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.config = mock.patch.dict(CFG, {"pasta": Path(self.pasta.name), "nome": "Miguel"})
        self.config.start()

    def tearDown(self):
        self.config.stop()
        self.pasta.cleanup()


class TesteMemoria(ComPastaTemporaria):
    def test_guarda_no_assunto_certo_e_le_de_volta(self):
        memoria.guardar("minha namorada se chama Ana.")
        memoria.guardar("Eu odeio cebola")
        memoria.guardar("Meu CNPJ é 12.345")
        memoria.guardar("A senha do wifi é batata123")
        memoria.guardar("O Ultron nasceu num sábado")
        assuntos = {i["texto"]: i["assunto"] for i in memoria.ler()}
        self.assertEqual(assuntos, {"Minha namorada se chama Ana": "Pessoas", "Eu odeio cebola": "Gostos",
                                    "Meu CNPJ é 12.345": "Trabalho e estudo",
                                    "A senha do wifi é batata123": "Casa e rotina",
                                    "O Ultron nasceu num sábado": "Outras coisas"})
        texto = memoria.arquivo().read_text(encoding="utf-8")
        self.assertIn("## Pessoas\n- Minha namorada se chama Ana · ", texto)

    def test_nao_repete_e_apaga(self):
        a = memoria.guardar("Eu odeio cebola")
        b = memoria.guardar("eu odeio cebola!")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(memoria.ler()), 1)
        memoria.apagar(a["id"])
        self.assertEqual(memoria.ler(), [])
        with self.assertRaises(ValueError):
            memoria.apagar(a["id"])
        with self.assertRaises(ValueError):
            memoria.guardar("   ")

    def test_le_o_que_foi_escrito_a_mao(self):
        memoria.arquivo().write_text("# Memória\n\n## Pessoas\n- A mãe dele é a [[Rita]]\n\n## Viagens\n- Foi pra Roma\n",
                                     encoding="utf-8")
        self.assertEqual([(i["texto"], i["assunto"]) for i in memoria.ler()],
                         [("A mãe dele é a [[Rita]]", "Pessoas"), ("Foi pra Roma", "Viagens")])

    def test_grafo_liga_voce_assuntos_lembrancas_e_nomes_repetidos(self):
        a = memoria.guardar("Minha namorada se chama Ana")
        b = memoria.guardar("O aniversário da Ana é em maio")
        c = memoria.guardar("Eu odeio cebola")
        g = memoria.grafo()
        ids = {n["id"]: n for n in g["nos"]}
        self.assertEqual(ids["voce"]["nome"], "Miguel")
        self.assertIn("assunto:Pessoas", ids)
        self.assertIn("nome:Ana", ids)
        self.assertIn([a["id"], "nome:Ana"], g["ligacoes"])
        self.assertIn([b["id"], "nome:Ana"], g["ligacoes"])
        self.assertIn(["assunto:Gostos", c["id"]], g["ligacoes"])
        self.assertNotIn("nome:Eu", ids)

    def test_vai_pro_prompt_do_claude(self):
        self.assertIn("(nada guardado ainda)", memoria.para_o_prompt())
        memoria.guardar("Eu odeio cebola")
        self.assertIn("- Eu odeio cebola (gostos)", memoria.para_o_prompt())


class TesteComandosDaMemoria(ComPastaTemporaria):
    def test_lembra_que(self):
        self.assertEqual(tentar("Ultron, lembra que minha namorada se chama Ana."), "Guardado na memória, em pessoas.")
        self.assertEqual(memoria.ler()[0]["texto"], "Minha namorada se chama Ana")
        self.assertEqual(tentar("guarda aí que minha namorada se chama Ana"), "Isso eu já sabia.")

    def test_pergunta_nao_vira_lembranca(self):
        self.assertIsNone(tentar("Lembra que horas são?"))
        self.assertIsNone(tentar("Você lembra que dia é hoje?"))
        self.assertEqual(memoria.ler(), [])

    def test_esquece(self):
        memoria.guardar("Eu odeio cebola")
        self.assertEqual(tentar("esquece que eu odeio cebola"), "Pronto, esqueci.")
        self.assertEqual(tentar("esquece que eu odeio cebola"), "Não achei isso na memória.")


class TesteRotasDaMemoria(ComPastaTemporaria):
    @classmethod
    def setUpClass(cls):
        cls.servidor = criar_servidor(0)
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()

    def pedir(self, caminho, corpo=None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        with urllib.request.urlopen(urllib.request.Request(self.url + caminho, data=dados), timeout=5) as r:
            return json.loads(r.read())

    def test_guardar_ver_e_apagar(self):
        nova = self.pedir("/api/memoria", {"texto": "Eu odeio cebola"})
        d = self.pedir("/api/memoria")
        self.assertEqual(d["total"], 1)
        self.assertEqual(d["lembrancas"][0]["id"], nova["id"])
        self.assertTrue(any(n["tipo"] == "lembranca" for n in d["grafo"]["nos"]))
        self.pedir("/api/memoria/apagar", {"id": nova["id"]})
        self.assertEqual(self.pedir("/api/memoria")["total"], 0)
