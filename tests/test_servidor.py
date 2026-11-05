"""O servidor sobe e as rotas principais respondem (sem abrir o Claude nem chamar serviços de fora)."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from ultron.http.servidor import achar_rota, criar_servidor
from ultron.nucleo.config import CFG, ESTADO, WEB
from ultron.nucleo.log import log
from ultron.recursos import curriculo


class TesteServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        curriculo.iniciar(CFG["pasta"], ESTADO, CFG["nome"], log, WEB)  # o app.py faz isso ao subir
        cls.servidor = criar_servidor(0)  # porta 0 = qualquer uma livre
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()

    def pegar(self, caminho, corpo=None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + caminho, data=dados), timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as erro:
            return erro.code, erro.read()

    def test_tela(self):
        codigo, corpo = self.pegar("/")
        self.assertEqual(codigo, 200)
        self.assertIn(b"<html", corpo.lower())

    def test_rotas_json(self):
        for caminho in ("/api/config", "/api/paineis", "/api/provas", "/api/saude", "/api/curriculo/estado"):
            codigo, corpo = self.pegar(caminho)
            self.assertEqual(codigo, 200, caminho)
            json.loads(corpo)

    def test_nao_sai_da_pasta_web(self):
        self.assertEqual(self.pegar("/../.env")[0], 404)
        self.assertEqual(self.pegar("/%2e%2e/.env")[0], 404)
        self.assertEqual(self.pegar("/api/nao-existe", {})[0], 404)

    def test_json_quebrado_vira_400(self):
        req = urllib.request.Request(self.url + "/api/tarefa", data=b"{quebrado")
        with self.assertRaises(urllib.error.HTTPError) as erro:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(erro.exception.code, 400)

    def test_roteador(self):
        funcao, params = achar_rota("GET", "/api/voz/abc123")
        self.assertIsNotNone(funcao)
        self.assertEqual(params, {"id_fala": "abc123"})
        self.assertIsNone(achar_rota("POST", "/api/voz/abc123")[0])


if __name__ == "__main__":
    unittest.main()
