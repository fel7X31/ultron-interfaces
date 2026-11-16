"""Quando uma IA chega no limite do plano: anotar até quando, passar pra próxima e voltar quando libera.
Sem chamar IA de verdade e sem mexer no .estado de verdade."""
import datetime as dt
import io
import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from ultron.assistente import cerebro, sessao, turno
from ultron.nucleo.config import CFG
from ultron.recursos import contas_ia, ias, limites

ERRO_DO_CODEX = ("ERROR: You’ve hit your usage limit. Upgrade to Plus to continue using Codex "
                 "(https://chatgpt.com/explore/plus), or try again at Nov 18th, 2026 8:30 AM.")


def sem_chave(nome, padrao=""):
    return padrao


class ComLimitesDeTeste(unittest.TestCase):
    """limites.json numa pasta temporária; prontos só o Claude e o ChatGPT (pela conta); escolhido o Claude Sonnet."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        for alvo in (mock.patch.object(limites, "ARQUIVO", Path(pasta.name) / "limites.json"),
                     mock.patch.object(contas_ia, "conectado", side_effect=lambda ia: ia == "chatgpt"),
                     mock.patch.object(ias, "variavel", side_effect=sem_chave),
                     mock.patch.dict(CFG, {"ia": "claude", "modelo": "sonnet"})):
            alvo.start()
            self.addCleanup(alvo.stop)


class TesteAnotacoes(ComLimitesDeTeste):
    def test_anota_ate_a_hora_e_depois_libera(self):
        agora = time.time()
        limites.esgotar("chatgpt", agora + 600, agora)
        self.assertEqual(limites.libera_em("chatgpt", agora=agora), agora + 600)
        self.assertIsNone(limites.libera_em("chatgpt", agora=agora + 601))
        self.assertIsNone(limites.libera_em("gemini", agora=agora))

    def test_sem_hora_tenta_de_novo_em_uma_hora(self):
        agora = time.time()
        self.assertEqual(limites.esgotar("gemini", None, agora), agora + limites.SEM_HORA_S)

    def test_limite_do_claude_inteiro_ou_de_um_modelo(self):
        limites.esgotar(limites.chave("claude", "seven_day_opus"))
        self.assertTrue(limites.libera_em("claude", "opus"))
        self.assertIsNone(limites.libera_em("claude", "sonnet"))
        limites.esgotar(limites.chave("claude", "five_hour"))
        self.assertTrue(limites.libera_em("claude", "sonnet"))

    def test_escolher_na_mao_esquece_o_limite(self):
        limites.esgotar("claude")
        limites.esgotar("claude:sonnet")
        limites.liberar("claude", "sonnet")
        self.assertIsNone(limites.libera_em("claude", "sonnet"))

    def test_arquivo_quebrado_nao_derruba(self):
        for conteudo in ("lixo", "[1, 2]", '{"claude": "amanhã"}'):
            limites.ARQUIVO.write_text(conteudo, encoding="utf-8")
            self.assertIsNone(limites.libera_em("claude", "sonnet"))


class TesteQuemResponde(ComLimitesDeTeste):
    def test_sem_limite_responde_a_escolhida(self):
        self.assertEqual(ias.quem_responde(), ("claude", "sonnet"))

    def test_claude_no_limite_passa_pra_proxima_pronta(self):
        limites.esgotar("claude")
        self.assertEqual(ias.quem_responde(), ("chatgpt", ""))

    def test_limite_da_semana_so_do_sonnet_vai_pro_opus(self):
        limites.esgotar("claude:sonnet")
        self.assertEqual(ias.quem_responde(), ("claude", "opus"))
        self.assertEqual(sessao.SessaoClaude().modelo_agora(), "opus")

    def test_outra_escolhida_no_limite_volta_pro_claude(self):
        CFG["ia"] = "chatgpt"
        limites.esgotar("chatgpt")
        self.assertEqual(ias.quem_responde(), ("claude", "sonnet"))

    def test_todas_no_limite_fica_a_escolhida(self):
        limites.esgotar("claude")
        limites.esgotar("chatgpt")
        self.assertEqual(ias.quem_responde(), ("claude", "sonnet"))

    def test_lista_mostra_quando_volta(self):
        limites.esgotar("chatgpt")
        opcoes = {o["ia"]: o for o in ias.opcoes()}
        self.assertTrue(opcoes["chatgpt"]["limite"].startswith("sem limite, volta "))
        self.assertEqual(opcoes["gemini"]["limite"], "")


class TesteAvisoDoClaude(unittest.TestCase):
    def ler(self, *mensagens):
        """Passa as linhas do Claude Code (stream-json) pela leitura da sessão e devolve o turno."""
        claude = sessao.SessaoClaude()
        claude.turno = sessao.TurnoClaude()
        claude._ler_saida(mock.Mock(stdout=[json.dumps(m) + "\n" for m in mensagens]))
        return claude.turno

    def test_aviso_de_limite_do_claude_code(self):
        turno_ = self.ler(
            {"type": "rate_limit_event",
             "rate_limit_info": {"status": "rejected", "resetsAt": 1763226000, "rateLimitType": "five_hour"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "You've hit your limit"}]}},
            {"type": "result", "is_error": True, "result": "You've hit your limit · resets 3pm"})
        r = sessao.com_limite(turno_.fila.get_nowait(), turno_.limite)
        self.assertEqual(r["limite"], {"ate": 1763226000.0, "tipo": "five_hour"})

    def test_hora_em_milissegundos(self):
        turno_ = self.ler({"type": "rate_limit_event",
                           "rate_limit_info": {"status": "rejected", "resetsAt": 1763226000000}})
        self.assertEqual(turno_.limite["ate"], 1763226000.0)

    def test_aviso_de_perto_do_limite_nao_conta(self):
        turno_ = self.ler({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning"}})
        self.assertIsNone(turno_.limite)

    def test_sem_o_aviso_vale_o_texto_do_erro(self):
        antigo = sessao.com_limite({"is_error": True, "result": "Claude AI usage limit reached|1763226000"})
        self.assertEqual(antigo["limite"]["ate"], 1763226000.0)
        novo = sessao.com_limite({"is_error": True, "result": "You've hit your limit · resets 3pm"})
        self.assertIsNone(novo["limite"]["ate"])

    def test_resposta_que_deu_certo_nao_e_limite(self):
        self.assertNotIn("limite", sessao.com_limite({"result": "Feito."}, {"ate": 1, "tipo": "five_hour"}))
        self.assertNotIn("limite", sessao.com_limite({"is_error": True, "result": "A sessão do Claude fechou."}))


class TesteSessaoTrocaDeModelo(ComLimitesDeTeste):
    def test_reabre_com_o_modelo_que_ainda_tem_limite(self):
        claude = sessao.SessaoClaude()
        antigo = mock.Mock(**{"poll.return_value": None})
        claude.proc, claude.modelo_aberto = antigo, "sonnet"

        def abrir():
            claude.proc, claude.modelo_aberto = mock.Mock(**{"poll.return_value": None}), claude.modelo_agora()

        limites.esgotar("claude:sonnet")
        with mock.patch.object(claude, "iniciar", side_effect=abrir) as iniciar, \
                mock.patch.object(claude, "_escrever", side_effect=lambda _: claude.turno.entregar({"result": "Ok."})):
            self.assertEqual(claude.perguntar("oi"), {"result": "Ok."})
        antigo.terminate.assert_called_once()
        iniciar.assert_called_once()
        self.assertEqual(claude.modelo_aberto, "opus")


class TesteContasSemCota(unittest.TestCase):
    def rodar_com_erro(self, erro):
        falhou = mock.Mock(returncode=1, stderr=erro, stdout="")
        with mock.patch.object(contas_ia.subprocess, "run", return_value=falhou):
            contas_ia._rodar(["codex"], "oi", 5)

    def test_codex_diz_quando_libera(self):
        with self.assertRaises(limites.SemCota) as erro:
            self.rodar_com_erro(ERRO_DO_CODEX)
        self.assertEqual(erro.exception.ate, dt.datetime(2026, 11, 18, 8, 30).timestamp())

    def test_hora_sem_data_e_de_hoje(self):
        ate = contas_ia._libera_em("You've hit your usage limit. Try again at 3:45 PM.", hoje=dt.date(2026, 11, 15))
        self.assertEqual(ate, dt.datetime(2026, 11, 15, 15, 45).timestamp())

    def test_cota_do_gemini_sem_hora(self):
        with self.assertRaises(limites.SemCota) as erro:
            self.rodar_com_erro("Error: Quota exceeded for quota metric 'Gemini Pro Requests'")
        self.assertIsNone(erro.exception.ate)

    def test_outra_falha_nao_e_limite(self):
        with self.assertRaises(OSError) as erro:
            self.rodar_com_erro("Error: connect ECONNREFUSED")
        self.assertNotIsInstance(erro.exception, limites.SemCota)

    def test_api_sem_cota_e_limite(self):
        recusa = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        chave = lambda nome, padrao="": "chave-de-teste" if nome == "XAI_API_KEY" else padrao  # noqa: E731
        with mock.patch.object(ias, "variavel", side_effect=chave), \
                mock.patch("urllib.request.urlopen", side_effect=recusa), self.assertRaises(limites.SemCota):
            ias.perguntar("grok", [])


class TesteTrocaNoTurno(ComLimitesDeTeste):
    CLAUDE_SEM_LIMITE = {"is_error": True, "result": "You've hit your limit", "limite": {"tipo": "five_hour"}}

    def setUp(self):
        super().setUp()
        for alvo in (mock.patch.object(turno, "prebusca", return_value=""),
                     mock.patch.object(cerebro, "log"), mock.patch.object(cerebro, "log_erro"),
                     mock.patch.object(cerebro.EVENTOS, "emitir")):
            alvo.start()
            self.addCleanup(alvo.stop)
        cerebro.CONVERSA.clear()
        self.addCleanup(cerebro.CONVERSA.clear)

    def perguntar(self):
        return turno._perguntar("oi", {}, time.time())

    def test_claude_no_limite_o_chatgpt_responde_e_continua_nele(self):
        with mock.patch.object(turno.SESSAO, "perguntar", return_value=self.CLAUDE_SEM_LIMITE) as claude, \
                mock.patch.object(ias, "perguntar", return_value="Tudo certo.") as chatgpt:
            primeira = self.perguntar()
            segunda = self.perguntar()
        self.assertTrue(primeira["result"].startswith("O Claude chegou no limite de uso, libera "))
        self.assertTrue(primeira["result"].endswith(" Passei pro ChatGPT. Tudo certo."))
        self.assertEqual(segunda, {"result": "Tudo certo."})
        claude.assert_called_once()
        self.assertEqual(chatgpt.call_count, 2)
        self.assertEqual(cerebro.nome_atual(), "ChatGPT")

    def test_todas_no_limite_conta_quando_cada_uma_volta(self):
        sem_cota = limites.SemCota(time.time() + 3 * 86400)
        with mock.patch.object(turno.SESSAO, "perguntar", return_value=self.CLAUDE_SEM_LIMITE), \
                mock.patch.object(ias, "perguntar", side_effect=sem_cota):
            r = self.perguntar()
        self.assertTrue(r["is_error"])
        self.assertIn("O Claude chegou no limite de uso, libera ", r["result"])
        self.assertIn("O ChatGPT chegou no limite de uso, libera dia ", r["result"])
        self.assertTrue(r["result"].endswith("Nenhuma outra IA tem limite agora."))

    def test_outra_ia_sabe_quando_o_claude_volta(self):
        limites.esgotar("claude")
        with mock.patch.object(ias, "perguntar", return_value="Ok.") as perguntar:
            cerebro.perguntar_a_outra_ia("abre o meu e-mail", "chatgpt")
        self.assertIn("que chegou no limite de uso e volta", perguntar.call_args[0][1][0]["content"])

    def test_quando_o_limite_libera_a_tela_mostra_a_volta(self):
        with mock.patch.dict(cerebro.MOSTRADO, {"nome": "ChatGPT"}):
            cerebro.conferir_quem_responde()
            cerebro.conferir_quem_responde()  # não repete enquanto não muda
        cerebro.EVENTOS.emitir.assert_called_once_with({"tipo": "ia", "nome": "Claude Sonnet"})

    def test_escolher_na_mao_tenta_de_novo(self):
        limites.esgotar("claude")
        with mock.patch.object(cerebro, "salvar_preferencias"):
            self.assertEqual(cerebro.escolher("claude", "sonnet"), "Claude Sonnet")
        self.assertIsNone(limites.libera_em("claude", "sonnet"))


if __name__ == "__main__":
    unittest.main()
