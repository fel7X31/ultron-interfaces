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
FECHADA = (132, 34)         # o entalhe compacto, em px da página (a LARGURA_COMPACTA do barra.js; com música, 470)
JANELA = (900, 548)         # a janela tem sempre o tamanho do painel aberto (LARGURA_ABERTA e ALTURA_ABERTA do barra.js)
FUNDO = {"prata": "#cfd2d6", "escuro": "#0b0c0e"}  # a cor antes da página carregar (evita um clarão)
NA_FRENTE, SEM_ATIVAR, SO_FICAR_NA_FRENTE = -1, 0x10, 0x13
MOSTRAR_SEM_ATIVAR, ESCONDER = 4, 0
CANTOS, ARREDONDADOS, COR_DA_BORDA, SEM_BORDA = 33, 2, 34, 0xFFFFFFFE
ESTILO, MINIMIZAR_E_MAXIMIZAR = -16, 0x30000
ESTILO_EXTRA, DE_FERRAMENTA, DE_APP = -20, 0x80, 0x40000
TELA_PRINCIPAL, MONITOR_MAIS_PERTO = 1, 2
JA_EXISTE = 183
COM_BARRA_DE_TITULO, SEMPRE_NA_FRENTE = 0x00C00000, 0x8
TELA_OCUPADA = (2, 3, 4)  # o Windows diz: app em tela cheia, jogo DirectX em tela cheia ou apresentação
ANIMACAO_S = 0.22         # quanto o painel leva pra abrir ou minimizar
QUADRO_S = 1 / 120        # um quadro da animação (o timer de 1 ms do main() deixa o sleep chegar perto disso)
RAIO = 18                 # o arredondado do recorte enquanto ele cresce ou encolhe, em px da página

user32 = ctypes.WinDLL("user32")
shell32 = ctypes.WinDLL("shell32")
gdi32 = ctypes.WinDLL("gdi32")
gdi32.CreateRoundRectRgn.restype = gdi32.CreateRectRgn.restype = wintypes.HRGN
user32.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN]
gdi32.GetRgnBox.argtypes = [wintypes.HRGN, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
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
        self._parte = FECHADA        # o pedaço da janela à vista agora, em px da página
        self._trava = threading.Lock()  # uma animação de cada vez
        self._ordem = 0              # o último pedido de tamanho que valeu (a página numera cada um)

    def expandir(self, largura, altura, ordem=None):
        """Abre o painel, crescendo do entalhe."""
        if self._mudar(largura, altura, ordem):
            user32.SetForegroundWindow(self._numero)  # o campo de pedido e o Esc precisam do teclado

    def recolher(self, largura=FECHADA[0], ordem=None):
        """Minimiza o painel até o entalhe, ou só muda a largura do entalhe (compacto ou com a música)."""
        self._mudar(largura, FECHADA[1], ordem)

    def _mudar(self, largura, altura, ordem=None):
        """Abre, minimiza ou muda a largura do entalhe mexendo só no recorte: a janela fica sempre do tamanho do painel.
        Mudar o tamanho dela fazia a página se redesenhar no meio da animação, e enquanto isso aparecia um cinza.

        O pywebview roda cada chamada da página numa thread: um "abrir" pode chegar depois do "minimizar" que veio
        depois dele. Pelo número da ordem, pedido atrasado não vale. Devolve se mudou."""
        with self._trava:
            if ordem is not None:
                if ordem < self._ordem:
                    return False
                self._ordem = ordem
            de, para = self._parte, (min(largura, JANELA[0]), min(altura, JANELA[1]))
            if de != para:
                self._animar_recorte(de, para)
            self._parte = para
            self._recortar(para)
            return True

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
        with self._trava:
            self._colocar()
        threading.Thread(target=self._vigiar, daemon=True).start()

    def _animar_recorte(self, de, para):
        """O pedaço que aparece vai do tamanho `de` até `para` (px da página), rápido no começo e suave no fim.
        Cada quadro vê quanto tempo passou: se um atrasar, o próximo compensa e a animação não se arrasta."""
        inicio = time.perf_counter()
        while True:
            passou = min(1.0, (time.perf_counter() - inicio) / ANIMACAO_S)
            t = 1 - (1 - passou) ** 3
            self._recortar((de[0] + (para[0] - de[0]) * t, de[1] + (para[1] - de[1]) * t))
            if passou >= 1:
                return
            time.sleep(QUADRO_S)

    def _recortar(self, parte):
        """Só aparece (e recebe clique) a `parte` da janela, no meio do topo; o resto deixa o clique passar. Em px da
        página."""
        x, largura, altura, raio = self._recorte_em_px(parte)
        user32.SetWindowRgn(self._numero, gdi32.CreateRoundRectRgn(x, 0, x + largura + 1, altura + 1, raio, raio), True)

    def _recorte_em_px(self, parte):
        escala = self._escala()
        largura, altura = round(parte[0] * escala), round((parte[1] + ESCONDIDO) * escala)
        return (round(JANELA[0] * escala) - largura) // 2, largura, altura, round(RAIO * escala)

    def _colocar(self):
        """No meio do topo da tela principal, com ESCONDIDO px acima dela, do tamanho do painel e recortada na parte
        de agora (o recorte entra antes, pra janela inteira não piscar)."""
        self._recortar(self._parte)
        escala = self._escala()
        l, a = round(JANELA[0] * escala), round((JANELA[1] + ESCONDIDO) * escala)
        x = (user32.GetSystemMetrics(0) - l) // 2
        user32.SetWindowPos(self._numero, NA_FRENTE, x, -round(ESCONDIDO * escala), l, a, SEM_ATIVAR)

    def _escala(self):
        return user32.GetDpiForWindow(self._numero) / 96

    def _vigiar(self):
        while True:
            self._conferir_visibilidade()
            self._conferir_tamanho()
            time.sleep(0.5)

    def _conferir_tamanho(self):
        """Fora de uma animação, a janela tem que estar do tamanho do painel e recortada na parte combinada. Se não
        está (o Windows ou o WinForms mexeram nela), volta pro certo."""
        if not self._trava.acquire(blocking=False):
            return
        try:
            escala, janela, caixa = self._escala(), _Retangulo(), _Retangulo()
            user32.GetWindowRect(self._numero, ctypes.byref(janela))
            certo = (round(JANELA[0] * escala), round((JANELA[1] + ESCONDIDO) * escala))
            regiao = gdi32.CreateRectRgn(0, 0, 0, 0)
            tem_recorte = user32.GetWindowRgn(self._numero, regiao) != 0
            gdi32.GetRgnBox(regiao, ctypes.byref(caixa))
            gdi32.DeleteObject(regiao)
            x, largura, _, _ = self._recorte_em_px(self._parte)
            if ((janela.direita - janela.esquerda, janela.baixo - janela.cima) != certo or not tem_recorte
                    or abs(caixa.esquerda - x) > 2 or abs(caixa.direita - caixa.esquerda - largura) > 2):
                self._colocar()
        finally:
            self._trava.release()

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
        if not user32.GetWindowLongW(self._numero, ESTILO_EXTRA) & SEMPRE_NA_FRENTE:  # só se perdeu: forçar a
            user32.SetWindowPos(self._numero, NA_FRENTE, 0, 0, 0, 0, SO_FICAR_NA_FRENTE)  # toda hora atrapalha jogos


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

    Primeiro pergunta pro Windows (o mesmo aviso que ele usa pra calar as notificações durante jogos). Depois confere a
    janela da frente: cobrindo a tela inteira e sem barra de título. Janela maximizada comum (com barra de título) não
    conta: com a barra de tarefas escondida, ela também cobre a tela inteira. Jogo em tela cheia sem borda conta.
    """
    ocupada = ctypes.c_int(0)
    if shell32.SHQueryUserNotificationState(ctypes.byref(ocupada)) == 0 and ocupada.value in TELA_OCUPADA:
        return True
    frente = user32.GetForegroundWindow()
    if not frente or frente == barra or _classe(frente) in janelas.DO_WINDOWS:
        return False
    if user32.IsZoomed(frente) and user32.GetWindowLongW(frente, ESTILO) & COM_BARRA_DE_TITULO:
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
    ctypes.WinDLL("winmm").timeBeginPeriod(1)  # sleep de 1 ms em vez de 15: a animação sai sem tranco
    barra = Barra()
    janela = webview.create_window(
        "Barra do Ultron", f"{URL}/barra.html", js_api=barra, width=JANELA[0], height=JANELA[1] + ESCONDIDO,
        frameless=True, on_top=True, resizable=False, easy_drag=False, shadow=False, hidden=True,
        min_size=(100, 30), background_color=FUNDO.get(CFG["tema"], FUNDO["escuro"]))
    webview.start(barra._comecar, janela)


if __name__ == "__main__":
    main()
