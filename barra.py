#!/usr/bin/env python3
"""Barra do Ultron no topo da tela (Windows): aparece quando a tela do Ultron está minimizada ou fechada.

Fechada, é um entalhe pendurado no meio do topo da tela. Clicando, abre um painel com o uso do PC, a música, o
volume, atalhos e um campo pra pedir algo ao Ultron. A página é a web/barra.html, servida pelo próprio Ultron;
este arquivo só cuida da janela: posição, tamanho, aparecer e sumir.

O Ultron abre a barra sozinho quando liga (ULTRON_BARRA=0 no .env desliga). Pra abrir na mão: py barra.py
Precisa de: py -m pip install -r requirements-barra.txt
"""
import ctypes
import threading
import time
import webbrowser
from ctypes import wintypes

import webview

from ultron.nucleo.config import CFG
from ultron.recursos.pc import janelas

URL = f"http://127.0.0.1:{CFG['porta']}"
ESCONDIDO = 12              # px da janela acima da tela: os cantos de cima somem e sobra o entalhe (igual ao barra.css)
FECHADA = (240, 34)         # largura e altura do entalhe, em px da página
FUNDO = {"prata": "#cfd2d6", "escuro": "#0b0c0e"}  # a cor antes da página carregar (evita um clarão)
NA_FRENTE, SEM_ATIVAR, SO_FICAR_NA_FRENTE = -1, 0x10, 0x13
MOSTRAR_SEM_ATIVAR, ESCONDER = 4, 0
CANTOS, ARREDONDADOS, COR_DA_BORDA, SEM_BORDA = 33, 2, 34, 0xFFFFFFFE
ESTILO, MINIMIZAR_E_MAXIMIZAR = -16, 0x30000
ESTILO_EXTRA, DE_FERRAMENTA, DE_APP = -20, 0x80, 0x40000
TELA_PRINCIPAL, MONITOR_MAIS_PERTO = 1, 2
JA_EXISTE = 183

user32 = ctypes.WinDLL("user32")
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [ctypes.c_uint]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _Retangulo(ctypes.Structure):
    _fields_ = [("esquerda", ctypes.c_long), ("cima", ctypes.c_long), ("direita", ctypes.c_long), ("baixo", ctypes.c_long)]


class _Monitor(ctypes.Structure):
    _fields_ = [("tamanho", wintypes.DWORD), ("tela", _Retangulo), ("area_util", _Retangulo), ("jeito", wintypes.DWORD)]


class Barra:
    """A janela da barra. Os métodos sem _ são os que a página chama (window.pywebview.api.*)."""

    def __init__(self):
        self._janela = None
        self._numero = None          # o identificador da janela no Windows
        self._quer_aparecer = False  # o que a página pediu (o Ultron diz se a tela dele está à vista)

    def expandir(self, largura, altura):
        self._colocar(largura, altura)
        user32.SetForegroundWindow(self._numero)  # o campo de pedido e o Esc precisam do teclado

    def recolher(self, largura=FECHADA[0]):
        self._colocar(largura, FECHADA[1])

    def aparecer(self, sim):
        self._quer_aparecer = bool(sim)
        self._conferir_visibilidade()

    def abrir_ultron(self):
        try:
            janelas.focar_tela_do_ultron()
        except ValueError:
            webbrowser.open(URL)

    def sair(self):
        self._janela.destroy()

    def _comecar(self, janela):
        """Roda quando a janela existe: cantos redondos, tamanho fechado e o vigia que mantém a barra no lugar."""
        janela.events.before_show.wait(10)
        janela.events.loaded.wait(20)  # o WinForms termina de montar a janela (e de mexer no estilo dela) antes
        self._janela = janela
        self._numero = janela.native.Handle.ToInt32()
        _arredondar(self._numero)
        self.recolher()
        threading.Thread(target=self._vigiar, daemon=True).start()

    def _colocar(self, largura, altura):
        """No meio do topo da tela principal, com ESCONDIDO px acima dela."""
        escala = user32.GetDpiForWindow(self._numero) / 96
        largura, altura = round(largura * escala), round((altura + ESCONDIDO) * escala)
        x = (user32.GetSystemMetrics(0) - largura) // 2
        user32.SetWindowPos(self._numero, NA_FRENTE, x, -round(ESCONDIDO * escala), largura, altura, SEM_ATIVAR)

    def _vigiar(self):
        while True:
            self._conferir_visibilidade()
            time.sleep(1)

    def _conferir_visibilidade(self):
        """Aparece quando a página pede, menos com jogo ou vídeo em tela cheia na tela principal.

        Confere a janela de verdade toda vez: o Win+D, outros programas e o próprio WinForms podem ter minimizado,
        escondido, passado na frente ou mudado o jeito dela.
        """
        if not self._numero:
            return
        if not self._quer_aparecer or _tela_cheia_na_frente(self._numero):
            if user32.IsWindowVisible(self._numero):
                user32.ShowWindow(self._numero, ESCONDER)
            return
        if _manter_jeito_de_entalhe(self._numero):
            user32.ShowWindow(self._numero, ESCONDER)  # esconder e mostrar de novo tira o botão da barra de tarefas
        if not user32.IsWindowVisible(self._numero) or user32.IsIconic(self._numero):
            user32.ShowWindow(self._numero, MOSTRAR_SEM_ATIVAR)
        user32.SetWindowPos(self._numero, NA_FRENTE, 0, 0, 0, 0, SO_FICAR_NA_FRENTE)


def _arredondar(numero):
    """Cantos arredondados do Windows 11 e sem a borda fina."""
    for atributo, valor in ((CANTOS, ARREDONDADOS), (COR_DA_BORDA, SEM_BORDA)):
        escolha = ctypes.c_uint(valor)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(numero, atributo, ctypes.byref(escolha), ctypes.sizeof(escolha))


def _manter_jeito_de_entalhe(numero):
    """Sem minimizar e maximizar (assim o Win+D não leva a barra junto) e fora da barra de tarefas e do Alt+Tab.
    Devolve se precisou mudar alguma coisa."""
    estilo, extra = user32.GetWindowLongW(numero, ESTILO), user32.GetWindowLongW(numero, ESTILO_EXTRA)
    estilo_certo, extra_certo = estilo & ~MINIMIZAR_E_MAXIMIZAR, (extra | DE_FERRAMENTA) & ~DE_APP
    if (estilo, extra) == (estilo_certo, extra_certo):
        return False
    user32.SetWindowLongW(numero, ESTILO, estilo_certo)
    user32.SetWindowLongW(numero, ESTILO_EXTRA, extra_certo)
    return True


def _tela_cheia_na_frente(barra):
    """Jogo, vídeo ou apresentação em tela cheia, na frente de tudo, na tela principal (onde fica a barra)?
    Janela maximizada não conta: com a barra de tarefas escondida, ela também cobre a tela inteira."""
    frente = user32.GetForegroundWindow()
    if not frente or frente == barra or user32.IsZoomed(frente) or _classe(frente) in janelas.DO_WINDOWS:
        return False
    monitor = _Monitor(tamanho=ctypes.sizeof(_Monitor))
    user32.GetMonitorInfoW(user32.MonitorFromWindow(frente, MONITOR_MAIS_PERTO), ctypes.byref(monitor))
    janela, tela = _Retangulo(), monitor.tela
    user32.GetWindowRect(frente, ctypes.byref(janela))
    cobre_tudo = janela.esquerda <= tela.esquerda and janela.cima <= tela.cima and \
        janela.direita >= tela.direita and janela.baixo >= tela.baixo
    return bool(monitor.jeito & TELA_PRINCIPAL) and cobre_tudo


def _classe(numero):
    nome = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(numero, nome, 64)
    return nome.value


def _sou_a_unica():
    """Só uma barra por vez: o nome fica reservado enquanto este processo estiver vivo."""
    global _RESERVA
    _RESERVA = kernel32.CreateMutexW(None, False, "UltronBarraDoTopo")
    return ctypes.get_last_error() != JA_EXISTE


def main():
    if not _sou_a_unica():
        return
    barra = Barra()
    janela = webview.create_window(
        "Barra do Ultron", f"{URL}/barra.html", js_api=barra, width=FECHADA[0], height=FECHADA[1] + ESCONDIDO,
        frameless=True, on_top=True, resizable=False, easy_drag=False, shadow=False, hidden=True,
        min_size=(100, 30), background_color=FUNDO.get(CFG["tema"], FUNDO["escuro"]))
    webview.start(barra._comecar, janela)


if __name__ == "__main__":
    main()
