"""Apertar teclas como se fosse no teclado (teclas de mídia, Win+D...) e digitar texto."""
import ctypes
from ctypes import wintypes

SOLTAR = 0x2
ESTENDIDA = 0x1  # teclas de mídia e de volume são "estendidas"
LETRA = 0x4      # manda o caractere em si, não a tecla: qualquer letra, em qualquer layout de teclado


class _Tecla(ctypes.Structure):
    _fields_ = [("tecla", wintypes.WORD), ("letra", wintypes.WORD), ("jeito", wintypes.DWORD),
                ("hora", wintypes.DWORD), ("extra", ctypes.c_size_t)]


class _Entrada(ctypes.Structure):  # o INPUT do Windows, só com a parte de teclado (o resto é espaço)
    _fields_ = [("tipo", wintypes.DWORD), ("teclado", _Tecla), ("sobra", ctypes.c_ubyte * 8)]


def digitar(texto):
    """Digita o texto na janela da frente, como se fosse no teclado."""
    entradas = [_Entrada(1, _Tecla(0, ord(c), jeito)) for c in texto for jeito in (LETRA, LETRA | SOLTAR)]
    lista = (_Entrada * len(entradas))(*entradas)
    ctypes.windll.user32.SendInput(len(lista), lista, ctypes.sizeof(_Entrada))


def apertar(*teclas, estendida=False):
    """Aperta as teclas juntas e solta na ordem contrária (ex.: apertar(VK_WIN, ord("D")) = Win+D)."""
    user32 = ctypes.windll.user32
    extra = ESTENDIDA if estendida else 0
    for tecla in teclas:
        user32.keybd_event(tecla, 0, extra, 0)
    for tecla in reversed(teclas):
        user32.keybd_event(tecla, 0, extra | SOLTAR, 0)
