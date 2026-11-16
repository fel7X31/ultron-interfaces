"""Janelas abertas no Windows: listar, trazer pra frente, minimizar, maximizar e fechar.

Acha a janela pelo nome do programa ("chrome", "spotify") ou por um pedaço do título ("youtube").
Só entram as janelas de app (as do Alt+Tab): a barra de tarefas e a área de trabalho ficam de fora.
"""
import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

from ...nucleo.texto import normalizar
from . import teclado

DO_WINDOWS = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}  # barra de tarefas e fundo
TELA_DO_ULTRON = "ULTRON"  # o título da tela dele: "fecha o navegador" nunca fecha ela junto
DONO, ESTILO_EXTRA, DE_FERRAMENTA, ESCONDIDA_PELO_WINDOWS = 4, -20, 0x80, 14
MINIMIZAR, MAXIMIZAR, RESTAURAR, FECHAR = 6, 3, 9, 0x10
LER_INFORMACOES = 0x1000
VK_WIN = 0x5B


@dataclass
class Janela:
    numero: int     # o identificador da janela no Windows
    titulo: str
    programa: str   # nome do .exe, minúsculo e sem a extensão


def listar():
    """As janelas de app abertas, como no Alt+Tab."""
    achadas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(numero, _):
        if _e_de_app(numero):
            achadas.append(Janela(numero, _titulo(numero), _programa(numero)))
        return True

    ctypes.windll.user32.EnumWindows(cada, 0)
    return achadas


def achar(nome):
    """As janelas do programa `nome` ou com `nome` no título. ValueError se não houver nenhuma."""
    alvo = " ".join(normalizar(nome))
    achadas = [j for j in listar() if alvo and (j.programa == alvo.replace(" ", "")
                                                or alvo in " ".join(normalizar(j.titulo)))]
    if not achadas:
        raise ValueError(f"Não achei janela de {nome} aberta.")
    return achadas


def focar(nome):
    """Traz pra frente a primeira janela achada (e restaura, se estava minimizada)."""
    janela = achar(nome)[0]
    trazer_pra_frente(janela.numero)
    return janela


def focar_tela_do_ultron():
    """Traz a tela do Ultron pra frente (pelo título dela). ValueError se ela não estiver aberta."""
    for janela in listar():
        if janela.titulo.startswith(TELA_DO_ULTRON):
            trazer_pra_frente(janela.numero)
            return janela
    raise ValueError("A tela do Ultron não está aberta.")


def minimizar(nome):
    """Minimiza todas as janelas achadas. Devolve quantas."""
    achadas = achar(nome)
    for janela in achadas:
        ctypes.windll.user32.ShowWindow(janela.numero, MINIMIZAR)
    return len(achadas)


def maximizar(nome):
    """Maximiza a primeira janela achada e traz pra frente."""
    janela = achar(nome)[0]
    ctypes.windll.user32.ShowWindow(janela.numero, MAXIMIZAR)
    trazer_pra_frente(janela.numero)
    return janela


def fechar(nome):
    """Pede pra fechar as janelas achadas, como clicar no X (o programa ainda pode perguntar se quer salvar)."""
    achadas = [j for j in achar(nome) if not j.titulo.startswith(TELA_DO_ULTRON)]
    for janela in achadas:
        ctypes.windll.user32.PostMessageW(janela.numero, FECHAR, 0, 0)
    return len(achadas)


def area_de_trabalho():
    """Win+D: mostra a área de trabalho (de novo, volta as janelas)."""
    teclado.apertar(VK_WIN, ord("D"))


def trazer_pra_frente(numero):
    """Restaura, se precisar, e põe a janela na frente.

    O Windows só deixa trocar a janela da frente quem está mexendo nela: por isso o Ultron se junta por um
    instante à fila de teclado da janela atual.
    """
    user32 = ctypes.windll.user32
    if user32.IsIconic(numero):
        user32.ShowWindow(numero, RESTAURAR)
    da_frente = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    minha = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(minha, da_frente, True)
    user32.SetForegroundWindow(numero)
    user32.BringWindowToTop(numero)
    user32.AttachThreadInput(minha, da_frente, False)


def _e_de_app(numero):
    user32 = ctypes.windll.user32
    if not user32.IsWindowVisible(numero) or user32.GetWindow(numero, DONO) or not _titulo(numero):
        return False
    if user32.GetWindowLongW(numero, ESTILO_EXTRA) & DE_FERRAMENTA or _classe(numero) in DO_WINDOWS:
        return False
    return not _escondida_pelo_windows(numero)


def _escondida_pelo_windows(numero):
    """Apps da loja suspensos e janelas de outra área de trabalho virtual contam como visíveis, mas não estão."""
    escondida = ctypes.c_int()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(numero, ESCONDIDA_PELO_WINDOWS, ctypes.byref(escondida),
                                               ctypes.sizeof(escondida))
    return bool(escondida.value)


def _titulo(numero):
    tamanho = ctypes.windll.user32.GetWindowTextLengthW(numero)
    texto = ctypes.create_unicode_buffer(tamanho + 1)
    ctypes.windll.user32.GetWindowTextW(numero, texto, tamanho + 1)
    return texto.value


def _classe(numero):
    nome = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(numero, nome, 256)
    return nome.value


def _programa(numero):
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(numero, ctypes.byref(pid))
    processo = kernel32.OpenProcess(LER_INFORMACOES, False, pid.value)
    if not processo:
        return ""
    try:
        caminho, tamanho = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        kernel32.QueryFullProcessImageNameW(wintypes.HANDLE(processo), 0, caminho, ctypes.byref(tamanho))
        return os.path.splitext(os.path.basename(caminho.value))[0].lower()
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(processo))
