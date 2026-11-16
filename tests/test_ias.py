"""Outras IAs (ChatGPT, Gemini, Grok) e a troca de quem responde. Sem chamar API nem programa de verdade."""
import io
import json
import unittest
import urllib.error
from unittest import mock

from ultron.assistente import cerebro, comandos
from ultron.nucleo.config import CFG
from ultron.recursos import contas_ia, ias

CHAVES = {"GEMINI_API_KEY": "chave-de-teste"}


def variavel_de_teste(nome, padrao=""):
    return CHAVES.get(nome) or padrao


def resposta_da_api(texto):
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": texto}}]}).encode())


def tentar(texto):
    registro = {}
    return comandos.tentar(comandos.Fala(texto, False, registro)), registro


@mock.patch.object(contas_ia, "conectado", return_value=False)
@mock.patch.object(ias, "variavel", side_effect=variavel_de_teste)
class TesteIas(unittest.TestCase):
    def test_opcoes_mostram_quem_tem_chave(self, *_):
        opcoes = {(o["ia"], o["modelo"]): o for o in ias.opcoes()}
        self.assertTrue(opcoes[("claude", "opus")]["ligada"])
        self.assertTrue(opcoes[("gemini", "gemini-3.8-flash")]["ligada"])
        self.assertFalse(opcoes[("chatgpt", "gpt-6.1-terra")]["ligada"])
        self.assertEqual(opcoes[("chatgpt", "gpt-6.1-terra")]["entrar"], "ChatGPT")
        self.assertEqual(opcoes[("grok", "grok-4.7")]["entrar"], "")

    def test_pergunta_no_formato_chat_completions(self, *_):
        with mock.patch("urllib.request.urlopen", return_value=resposta_da_api(" Olá. ")) as abrir:
            self.assertEqual(ias.perguntar("gemini", [{"role": "user", "content": "oi"}]), "Olá.")
        pedido = abrir.call_args[0][0]
        corpo = json.loads(pedido.data)
        self.assertIn("generativelanguage.googleapis.com", pedido.full_url)
        self.assertEqual(pedido.get_header("Authorization"), "Bearer chave-de-teste")
        self.assertEqual(corpo["model"], "gemini-3.8-flash")
        self.assertEqual(corpo["reasoning_effort"], "low")

    def test_se_a_api_recusa_o_modo_rapido_tenta_o_padrao(self, *_):
        recusa = urllib.error.HTTPError("url", 400, "Bad Request", {}, io.BytesIO(b"{}"))
        with mock.patch("urllib.request.urlopen", side_effect=[recusa, resposta_da_api("Feito.")]) as abrir:
            self.assertEqual(ias.perguntar("gemini", []), "Feito.")
        self.assertNotIn("reasoning_effort", json.loads(abrir.call_args[0][0].data))

    def test_sem_chave_avisa(self, *_):
        with self.assertRaises(ValueError):
            ias.perguntar("chatgpt", [])

    def test_sem_chave_vai_pela_conta(self, *_):
        with mock.patch.object(contas_ia, "conectado", return_value=True), \
                mock.patch.object(contas_ia, "perguntar", return_value="Pela conta.") as pela_conta:
            self.assertEqual(ias.perguntar("chatgpt", [{"role": "user", "content": "oi"}]), "Pela conta.")
        self.assertEqual(pela_conta.call_args[0][0], "chatgpt")


class TesteContas(unittest.TestCase):
    def test_conversa_vira_um_texto_so(self):
        texto = contas_ia._conversa_em_texto([{"role": "system", "content": "Seja o Ultron."},
                                              {"role": "user", "content": "oi"},
                                              {"role": "assistant", "content": "Previsível."},
                                              {"role": "user", "content": "e agora?"}])
        self.assertTrue(texto.startswith("[INSTRUÇÕES]\nSeja o Ultron."))
        self.assertIn("[VOCÊ]\nPrevisível.", texto)
        self.assertTrue(texto.rstrip().endswith("sem usar ferramentas."))

    def test_gemini_le_a_resposta_do_json(self):
        with mock.patch.object(contas_ia, "_rodar", return_value='{"response": " Olá. ", "stats": {}}'), \
                mock.patch("shutil.which", return_value="gemini"):
            self.assertEqual(contas_ia.perguntar("gemini", [{"role": "user", "content": "oi"}]), "Olá.")

    def test_entrar_so_nas_que_tem_conta(self):
        with self.assertRaises(ValueError):
            contas_ia.entrar("grok")
        with mock.patch("shutil.which", return_value=None), self.assertRaises(ValueError):
            contas_ia.entrar("gemini")


@mock.patch.object(contas_ia, "conectado", return_value=False)
@mock.patch.object(ias, "variavel", side_effect=variavel_de_teste)
@mock.patch.object(cerebro, "salvar_preferencias")
class TesteCerebro(unittest.TestCase):
    def setUp(self):
        self.antes = (CFG["ia"], CFG["modelo"])

    def tearDown(self):
        CFG["ia"], CFG["modelo"] = self.antes
        cerebro.CONVERSA.clear()

    def test_trocar_pra_outra_ia_e_conversar(self, *_):
        self.assertEqual(cerebro.escolher("gemini"), "Gemini")
        self.assertFalse(cerebro.usando_claude())
        with mock.patch.object(ias, "perguntar", return_value="Previsível.") as perguntar:
            self.assertEqual(cerebro.perguntar_a_outra_ia("oi"), {"result": "Previsível."})
        self.assertIn("Gemini", perguntar.call_args[0][1][0]["content"])  # a persona diz em quem ele roda agora
        self.assertEqual(len(cerebro.CONVERSA), 2)

    def test_erro_da_outra_ia_vira_resposta(self, *_):
        cerebro.escolher("gemini")
        with mock.patch.object(ias, "perguntar", side_effect=OSError("caiu")), mock.patch.object(cerebro, "log_erro"):
            r = cerebro.perguntar_a_outra_ia("oi")
        self.assertTrue(r["is_error"])
        self.assertIn("Gemini", r["result"])

    def test_sem_chave_ou_desconhecida_nao_troca(self, *_):
        with self.assertRaises(ValueError):
            cerebro.escolher("chatgpt")
        with self.assertRaises(ValueError):
            cerebro.escolher("hal9000")
        self.assertEqual(CFG["ia"], self.antes[0])

    def test_trocar_o_modelo_do_claude_reabre_a_sessao(self, *_):
        CFG["modelo"] = "sonnet"
        with mock.patch.object(cerebro.SESSAO, "parar") as parar, mock.patch.object(cerebro.SESSAO, "iniciar"):
            self.assertEqual(cerebro.escolher("claude", "opus"), "Claude Opus")
            cerebro.escolher("claude", "opus")
        parar.assert_called_once()

    def test_comandos_de_voz(self, *_):
        with mock.patch.object(cerebro.SESSAO, "parar"), mock.patch.object(cerebro.SESSAO, "iniciar"):
            self.assertIn("Gemini", tentar("usa o Gemini")[0])
            self.assertIn("não está conectado", tentar("muda pro chat GPT")[0])
            self.assertIn("Claude", tentar("volta pro Cloud")[0])
            self.assertIn("Claude Opus", tentar("usa o opus")[0])
            self.assertIn("Claude Opus", tentar("qual modelo você está usando agora?")[0])
        self.assertIsNone(tentar("o que o gemini acha de um texto enorme sobre economia e política")[0])


if __name__ == "__main__":
    unittest.main()


class TesteLimiteDaConta(unittest.TestCase):
    ERRO = ("ERROR: You’ve hit your usage limit. Upgrade to Plus to continue using Codex "
            "(https://chatgpt.com/explore/plus), or try again at Nov 18th, 2026 8:30 AM.")

    def test_limite_vira_frase_em_portugues(self):
        falhou = mock.Mock(returncode=1, stderr=self.ERRO, stdout="")
        with mock.patch.object(contas_ia.subprocess, "run", return_value=falhou):
            with self.assertRaises(contas_ia.SemCota) as erro:
                contas_ia._rodar(["codex"], "oi", 5)
        self.assertEqual(str(erro.exception),
                         "a sua conta chegou no limite de uso do plano. Libera de novo em 18/11 às 8:30")

    def test_cerebro_conta_o_motivo(self):
        sem_cota = contas_ia.SemCota("a sua conta chegou no limite de uso do plano")
        with mock.patch.dict(CFG, {"ia": "chatgpt"}), mock.patch.object(ias, "perguntar", side_effect=sem_cota):
            r = cerebro.perguntar_a_outra_ia("oi")
        self.assertTrue(r["is_error"])
        self.assertIn("limite de uso", r["result"])
