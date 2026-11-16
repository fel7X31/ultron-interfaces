import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ultron.recursos import icone

PNG = b"\x89PNG\r\n\x1a\nfake"


class TestIcone(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        patcher = mock.patch.object(icone, "ESTADO", Path(self.pasta.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sem_imagem_usa_o_robo(self):
        self.assertFalse(icone.situacao()["personalizado"])
        self.assertEqual(icone.imagem()[1], "image/svg+xml")

    def test_salvar_e_voltar(self):
        self.assertTrue(icone.salvar(PNG, "image/png")["personalizado"])
        self.assertEqual(icone.imagem(), (PNG, "image/png"))
        icone.salvar(b"jpg", "image/jpeg; charset=x")
        self.assertEqual(icone.imagem()[1], "image/jpeg")  # a anterior saiu
        self.assertFalse(icone.apagar()["personalizado"])

    def test_recusa_o_que_nao_e_imagem(self):
        with self.assertRaises(ValueError):
            icone.salvar(b"<html>", "text/html")
        with self.assertRaises(ValueError):
            icone.salvar(b"", "image/png")


if __name__ == "__main__":
    unittest.main()
