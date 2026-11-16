"""Lembretes (lembretes.md na pasta dele) e timers: entender o tempo falado, guardar, avisar e os comandos de voz."""
import datetime as dt
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ultron.assistente import comandos
from ultron.assistente.comandos_lembretes import texto_do_lembrete
from ultron.nucleo.config import CFG
from ultron.nucleo.texto import normalizar
from ultron.recursos import lembretes

AGORA = dt.datetime(2026, 11, 15, 14, 0)


def tentar(texto):
    return comandos.tentar(comandos.Fala(texto, False, {}))


def quando(frase, agora=AGORA):
    return lembretes.quando(normalizar(frase), agora)


class TesteTempoFalado(unittest.TestCase):
    def test_duracao(self):
        casos = {"5 minutos": 300, "uma hora e meia": 5400, "meia hora": 1800, "1h30": 5400, "30s": 30,
                 "vinte e cinco minutos": 1500, "2 horas e 15 minutos": 8100, "timer de 10": 600,
                 "tomar 2 comprimidos daqui a 10 minutos": 600, "sem tempo nenhum": None}
        for frase, segundos in casos.items():
            self.assertEqual(lembretes.duracao(normalizar(frase)), segundos, frase)

    def test_quando(self):
        self.assertEqual(quando("daqui a 10 minutos"), AGORA + dt.timedelta(minutes=10))
        self.assertEqual(quando("às 15h30"), AGORA.replace(hour=15, minute=30))
        self.assertEqual(quando("às 3 da tarde"), AGORA.replace(hour=15))
        self.assertEqual(quando("às 3"), AGORA.replace(hour=15))           # 3 da manhã já passou: 15h
        self.assertEqual(quando("às 9"), AGORA.replace(hour=21))
        self.assertEqual(quando("amanhã às 9"), AGORA.replace(day=16, hour=9))
        self.assertEqual(quando("às sete e meia da noite"), AGORA.replace(hour=19, minute=30))
        self.assertEqual(quando("às 13"), AGORA.replace(day=16, hour=13))  # já passou: amanhã
        self.assertEqual(quando("ao meio dia"), AGORA.replace(day=16, hour=12))
        self.assertIsNone(quando("de comprar pão"))

    def test_texto_do_lembrete(self):
        casos = {"Me lembra de ligar pra mãe às 19h.": "ligar pra mãe",
                 "Ultron, me lembra às 19h de ligar pra mãe": "ligar pra mãe",
                 "me avisa daqui a 10 minutos pra tirar o bolo do forno": "tirar o bolo do forno",
                 "Me lembra amanhã às 9 da manhã de pagar a conta de luz": "pagar a conta de luz",
                 "cria um lembrete de beber água em 30 minutos": "beber água"}
        for falado, texto in casos.items():
            self.assertEqual(texto_do_lembrete(falado), texto, falado)


class TesteLembretesETimers(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.config = mock.patch.dict(CFG, {"pasta": Path(self.pasta.name), "nome": "Miguel"})
        self.config.start()
        self.sem_voz = mock.patch.object(lembretes, "url_fala", return_value="")
        self.sem_voz.start()
        lembretes.TIMERS.clear()

    def tearDown(self):
        lembretes.TIMERS.clear()
        self.sem_voz.stop()
        self.config.stop()
        self.pasta.cleanup()

    def test_lembrete_avisa_uma_vez_na_hora(self):
        daqui_a_pouco = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(minutes=5)
        novo = lembretes.criar_lembrete("ligar pra mãe", daqui_a_pouco)
        self.assertIn(f"- [ ] {daqui_a_pouco:%Y-%m-%d %H:%M} · ligar pra mãe",
                      lembretes.arquivo().read_text(encoding="utf-8"))
        self.assertEqual(lembretes.conferir(daqui_a_pouco - dt.timedelta(minutes=1)), [])
        self.assertEqual(lembretes.conferir(daqui_a_pouco), ["Miguel, lembrete: ligar pra mãe."])
        self.assertEqual(lembretes.conferir(daqui_a_pouco + dt.timedelta(minutes=1)), [])
        self.assertTrue(lembretes.ler()[0]["feito"])
        self.assertEqual(lembretes.limpar_avisados(), 1)
        with self.assertRaises(ValueError):
            lembretes.apagar_lembrete(novo["id"])

    def test_nao_aceita_hora_que_passou(self):
        with self.assertRaises(ValueError):
            lembretes.criar_lembrete("algo", dt.datetime.now() - dt.timedelta(hours=1))

    def test_timer(self):
        timer = lembretes.criar_timer(300)
        self.assertEqual(timer["rotulo"], "Timer de 5 minutos")
        self.assertEqual(lembretes.listar()["timers"][0]["falta"], 300)
        fim = dt.datetime.fromtimestamp(timer["fim"] + 1)
        self.assertEqual(lembretes.conferir(fim), ["Miguel, acabou o timer de 5 minutos."])
        self.assertEqual(lembretes.listar()["timers"], [])
        with self.assertRaises(ValueError):
            lembretes.criar_timer(0)

    def test_comandos_de_voz(self):
        self.assertEqual(tentar("timer de 5 minutos"), "Timer de 5 minutos começando.")
        self.assertEqual(tentar("coloca um timer de meia hora"), "Timer de 30 minutos começando.")
        self.assertTrue(tentar("quanto falta no timer?").startswith("Faltam "))
        self.assertEqual(tentar("cancela o timer"), "2 timers cancelados.")
        self.assertEqual(tentar("cancela o timer"), "Não tem timer rodando.")
        resposta = tentar("me lembra de beber água daqui a 20 minutos")
        self.assertRegex(resposta, r"^Combinado\. (Às|Amanhã às) ")  # perto da meia-noite, 20 minutos já é amanhã
        self.assertTrue(resposta.endswith("eu te lembro: beber água."), resposta)
        self.assertEqual(lembretes.ler()[0]["texto"], "beber água")
        self.assertTrue(tentar("me lembra de comprar pão").startswith("Pra quando?"))
        self.assertTrue(tentar("quais são meus lembretes").startswith("1 lembrete."))
        self.assertIsNone(tentar("me lembra o que eu tinha que fazer hoje"))

    def test_timer_nao_vira_musica(self):
        self.assertEqual(tentar("coloca um timer de 10 minutos"), "Timer de 10 minutos começando.")
        self.assertLess(lembretes.listar()["timers"][0]["fim"], time.time() + 601)
