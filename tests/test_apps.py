"""Abrir programa pelo nome falado: achar o instalado mais parecido, sem abrir nada de verdade."""
import unittest
from unittest import mock

from ultron.recursos.pc import apps, programas

INSTALADOS = [
    {"nome": "Rocket League®", "como": "com.epicgames.launcher://apps/x?action=launch&silent=true"},
    {"nome": "Paint", "como": "shell:AppsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App"},
    {"nome": "Steam", "como": "C:/atalhos/Steam.lnk"},
    {"nome": "SteamVR", "como": "C:/atalhos/SteamVR.lnk"},
    {"nome": "EA SPORTS FC™ 26", "como": "C:/atalhos/FC 26.lnk"},
    {"nome": "Uninstall Steam", "como": "C:/atalhos/Desinstalar.lnk"},
]


class TesteAcharPrograma(unittest.TestCase):
    def achar(self, nome):
        app = apps.achar(nome, INSTALADOS)
        return app and app["nome"]

    def test_pelo_nome_falado(self):
        self.assertEqual(self.achar("rocket league"), "Rocket League®")
        self.assertEqual(self.achar("o paint"), "Paint")
        self.assertEqual(self.achar("Steam"), "Steam")  # não o SteamVR nem o desinstalador
        self.assertEqual(self.achar("fifa"), "EA SPORTS FC™ 26")

    def test_parecido_mas_nao_qualquer_coisa(self):
        self.assertEqual(self.achar("rocket legue"), "Rocket League®")  # a transcrição errou uma letra
        self.assertIsNone(self.achar("fortnite"))
        self.assertIsNone(self.achar(""))

    def test_sem_achar_avisa_sem_janela_de_erro(self):
        with mock.patch.object(apps, "catalogo", return_value=INSTALADOS), \
                mock.patch.object(programas.shutil, "which", return_value=None), \
                mock.patch.object(programas.os, "startfile", create=True) as abriu:
            with self.assertRaises(ValueError):
                programas.abrir("fortnite")
            self.assertEqual(programas.abrir("rocket league"), "Rocket League®")
        abriu.assert_called_once_with(INSTALADOS[0]["como"])

    def test_comando_de_voz_so_usa_a_lista_pronta(self):
        with mock.patch.object(apps, "guardado", return_value=INSTALADOS), \
                mock.patch.object(apps, "catalogo", side_effect=AssertionError("não pode montar na hora")):
            self.assertTrue(programas.conhecido("rocket league"))
            self.assertFalse(programas.conhecido("arquivo de ontem"))


if __name__ == "__main__":
    unittest.main()
