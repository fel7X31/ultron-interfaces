"""As rotas das seções novas da barra: lembretes e timers, copiados, conversa recente, chamar e a capa da música.
Nada mexe no PC de verdade: a área de transferência, o log e a capa são simulados."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from ultron.http.rotas import conversa
from ultron.http.servidor import criar_servidor
from ultron.nucleo.config import CFG
from ultron.recursos import copiados, lembretes
from ultron.recursos.pc import midia


class ComServidor(unittest.TestCase):
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
            return r.status, r.headers.get("Content-Type"), r.read()

    def pedir_json(self, caminho, corpo=None):
        return json.loads(self.pedir(caminho, corpo)[2])


class TesteLembretesETimers(ComServidor):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.config = mock.patch.dict(CFG, {"pasta": Path(self.pasta.name)})
        self.config.start()
        lembretes.TIMERS.clear()

    def tearDown(self):
        lembretes.TIMERS.clear()
        self.config.stop()
        self.pasta.cleanup()

    def test_lembrete_pela_barra(self):
        novo = self.pedir_json("/api/lembretes", {"texto": "ligar pra mãe", "quando": "2099-01-01T19:00"})
        self.assertEqual(novo["quando"], "2099-01-01 19:00")
        self.assertEqual(self.pedir_json("/api/lembretes")["lembretes"][0]["texto"], "ligar pra mãe")
        self.pedir_json("/api/lembretes/apagar", {"id": novo["id"]})
        self.assertEqual(self.pedir_json("/api/lembretes")["lembretes"], [])

    def test_hora_que_passou_vira_400(self):
        with self.assertRaises(urllib.error.HTTPError) as erro:
            self.pedir("/api/lembretes", {"texto": "algo", "quando": "2000-01-01T10:00"})
        self.assertEqual(erro.exception.code, 400)

    def test_timer_pela_barra(self):
        timer = self.pedir_json("/api/timers", {"segundos": 90, "nome": "pizza"})
        self.assertEqual(timer["rotulo"], "pizza")
        self.assertEqual(self.pedir_json("/api/lembretes")["timers"][0]["id"], timer["id"])
        self.assertEqual(self.pedir_json("/api/timers/cancelar", {"id": timer["id"]})["cancelados"], 1)


class TesteCopiados(ComServidor):
    def setUp(self):
        copiados.ITENS.clear()

    def tearDown(self):
        copiados.ITENS.clear()

    def test_guarda_sobe_o_repetido_e_apaga(self):
        copiados.guardar("primeiro")
        copiados.guardar("segundo")
        copiados.guardar("primeiro")
        self.assertEqual([i["texto"] for i in self.pedir_json("/api/copiados")["itens"]], ["primeiro", "segundo"])
        self.assertFalse(copiados.guardar("   "))
        with mock.patch.object(copiados, "_escrever") as escrever:
            self.pedir_json("/api/copiados/copiar", {"id": copiados.ITENS[1]["id"]})
        escrever.assert_called_once_with("segundo")
        self.pedir_json("/api/copiados/apagar", {"id": ""})
        self.assertEqual(copiados.ITENS, [])


class TesteConversaEChamar(ComServidor):
    def test_conversa_recente(self):
        with mock.patch.object(conversa, "conversa_recente", return_value=[{"voce": "oi", "resposta": "olá", "quando": ""}]):
            self.assertEqual(self.pedir_json("/api/conversa")["turnos"][0]["resposta"], "olá")

    def test_chamar_avisa_o_palmas_pelo_log(self):
        with mock.patch.object(conversa, "log") as log:  # o log de verdade faria o palmas.py abrir o microfone
            self.pedir_json("/api/chamar", {})
        log.assert_called_once_with({"evento": "chamar"})


class TesteCapa(ComServidor):
    def test_capa(self):
        with mock.patch.object(midia, "capa", return_value=None):
            with self.assertRaises(urllib.error.HTTPError) as erro:
                self.pedir("/api/pc/capa")
            self.assertEqual(erro.exception.code, 404)
        with mock.patch.object(midia, "capa", return_value=(b"\x89PNG...", "image/png")):
            status, tipo, corpo = self.pedir("/api/pc/capa")
        self.assertEqual((status, tipo, corpo), (200, "image/png", b"\x89PNG..."))
