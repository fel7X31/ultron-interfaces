"""Controle do PC: os comandos de voz e as ações. Nada aqui mexe no PC de verdade (tudo simulado com mock)."""
import unittest
from unittest import mock

from ultron.assistente import comandos
from ultron.recursos import pc
from ultron.recursos.pc import acoes, janelas, midia, programas


def tentar(texto):
    registro = {}
    return comandos.tentar(comandos.Fala(texto, False, registro)), registro


def acao_simulada(acao, alvo=""):
    return f"{acao}|{alvo}"


@mock.patch.object(pc, "executar", side_effect=acao_simulada)
class TesteComandosDoPC(unittest.TestCase):
    def test_volume(self, _):
        self.assertEqual(tentar("volume 30")[0], "volume|30")
        self.assertEqual(tentar("coloca o volume em cinquenta")[0], "volume|50")
        self.assertEqual(tentar("aumenta o volume")[0], "mais_volume|10")
        self.assertEqual(tentar("abaixa o volume em 20")[0], "menos_volume|20")
        self.assertEqual(tentar("abaixa o volume pra 20")[0], "volume|20")
        self.assertEqual(tentar("aumenta o som")[0], "mais_volume|10")

    def test_mudo(self, _):
        self.assertEqual(tentar("muta o pc")[0], "mudo|")
        self.assertEqual(tentar("tira o som")[0], "mudo|")
        self.assertEqual(tentar("desmuta")[0], "som|")

    def test_spotify_respeita_se_ja_esta_tocando(self, _):
        with mock.patch.object(midia, "tocando", return_value={"tocando": True}):
            self.assertEqual(tentar("pausa o spotify")[0], "tocar_pausar|")
            self.assertEqual(tentar("toca o spotify")[0], "Já está tocando.")
        with mock.patch.object(midia, "tocando", return_value={}):
            self.assertEqual(tentar("pausa o spotify")[0], "Já está pausado.")
            self.assertEqual(tentar("continua o spotify")[0], "tocar_pausar|")
        self.assertEqual(tentar("próxima música do spotify")[0], "proxima|")

    def test_programas_conhecidos_abrem_e_fecham_na_hora(self, _):
        self.assertEqual(tentar("abre o spotify")[0], "abrir|spotify")
        self.assertEqual(tentar("fecha a calculadora")[0], "fechar|calculadora")
        self.assertEqual(tentar("abre as configurações de bluetooth")[0], "configuracoes|bluetooth")

    def test_janelas_bloqueio_brilho_e_uso(self, _):
        self.assertEqual(tentar("bloqueia o computador")[0], "bloquear|")
        self.assertEqual(tentar("minimiza tudo")[0], "area_de_trabalho|")
        self.assertEqual(tentar("brilho 70")[0], "brilho|70")
        self.assertEqual(tentar("diminui o brilho")[0], "menos_brilho|20")
        self.assertEqual(tentar("como está o pc?")[0], "uso|")
        self.assertEqual(tentar("que música está tocando")[0], "tocando|")

    def test_o_resto_vai_pro_claude(self, executar):
        for frase in ("abre o arquivo de ontem", "fecha a aba do youtube", "qual a previsão do tempo",
                      "abre o projeto do currículo no vscode e roda os testes"):
            self.assertIsNone(tentar(frase)[0], frase)
        executar.assert_not_called()

    def test_musica_do_ultron_continua_com_o_player(self, executar):
        self.assertEqual(tentar("pausa a música")[0], "Pausei.")
        self.assertEqual(tentar("próxima música")[0], "Próxima.")
        executar.assert_not_called()


class TesteAcoes(unittest.TestCase):
    def test_acao_desconhecida_e_numero_errado(self):
        with self.assertRaises(ValueError):
            pc.executar("explodir")
        with self.assertRaises(ValueError):
            acoes._numero("alto", "O volume")
        self.assertEqual(acoes._numero("30%", "O volume"), 30)

    def test_volume_com_frase(self):
        with mock.patch.object(acoes.volume, "mudar", return_value={"nivel": 40, "mudo": False}) as mudar:
            self.assertEqual(pc.executar("volume", "40"), "Volume em 40.")
        mudar.assert_called_once_with(40)

    def test_tocando(self):
        with mock.patch.object(acoes.midia, "tocando", return_value={}):
            self.assertEqual(pc.executar("tocando"), "Nada tocando agora.")
        musica = {"titulo": "Numb", "artista": "Linkin Park", "app": "Spotify", "tocando": True}
        with mock.patch.object(acoes.midia, "tocando", return_value=musica):
            self.assertEqual(pc.executar("tocando"), "Tocando: Numb, de Linkin Park, no Spotify.")


class TesteJanelasEProgramas(unittest.TestCase):
    ABERTAS = [janelas.Janela(1, "ULTRON", "msedge"), janelas.Janela(2, "Vídeo - YouTube - Edge", "msedge"),
               janelas.Janela(3, "Calculadora", "applicationframehost")]

    def test_acha_pelo_programa_ou_pelo_titulo(self):
        with mock.patch.object(janelas, "listar", return_value=self.ABERTAS):
            self.assertEqual([j.numero for j in janelas.achar("msedge")], [1, 2])
            self.assertEqual([j.numero for j in janelas.achar("youtube")], [2])
            self.assertEqual([j.numero for j in janelas.achar("Calculadora")], [3])
            with self.assertRaises(ValueError):
                janelas.achar("spotify")

    def test_fechar_o_navegador_nao_fecha_a_tela_do_ultron(self):
        with mock.patch.object(janelas, "listar", return_value=self.ABERTAS), \
                mock.patch("ctypes.windll.user32.PostMessageW") as fechar:
            self.assertEqual(programas.fechar("navegador"), 1)
        self.assertEqual(fechar.call_args[0][0], 2)

    def test_programa_conhecido(self):
        self.assertTrue(programas.conhecido("Spotify"))
        self.assertTrue(programas.conhecido("bloco de notas"))
        self.assertFalse(programas.conhecido("arquivo de ontem"))

    def test_nome_do_app_que_toca(self):
        self.assertEqual(midia.nome_do_app("Spotify.exe"), "Spotify")
        self.assertEqual(midia.nome_do_app("chrome.exe"), "Chrome")
        self.assertEqual(midia.nome_do_app("Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic"), "ZuneMusic")


class TestePularVideo(unittest.TestCase):
    """Vídeo do YouTube fora de playlist não deixa o Windows pular: vai pelo atalho do site, na janela dele."""

    def test_usa_o_atalho_na_janela_do_video(self):
        video = janelas.Janela(7, "(2) Meu vídeo - YouTube - Samsung Internet", "samsunginternet")
        with mock.patch.object(midia, "tocando", return_value={"titulo": "Meu vídeo", "proxima": False}), \
                mock.patch.object(janelas, "listar", return_value=[video]), \
                mock.patch.object(janelas, "trazer_pra_frente") as frente, \
                mock.patch.object(midia.teclado, "apertar") as apertou, mock.patch.object(midia.time, "sleep"):
            midia.apertar("proxima")
        apertou.assert_called_once_with(0x10, ord("N"), estendida=False)
        self.assertEqual(frente.call_args_list[0], mock.call(7))

    def test_sem_a_janela_do_video_avisa(self):
        with mock.patch.object(midia, "tocando", return_value={"titulo": "Outro vídeo", "anterior": False}), \
                mock.patch.object(janelas, "listar", return_value=[]), self.assertRaises(ValueError):
            midia.apertar("anterior")


if __name__ == "__main__":
    unittest.main()
