"""Apertar teclas como se fosse no teclado (teclas de mídia, Win+D...)."""
import ctypes

SOLTAR = 0x2
ESTENDIDA = 0x1  # teclas de mídia e de volume são "estendidas"


def apertar(*teclas, estendida=False):
    """Aperta as teclas juntas e solta na ordem contrária (ex.: apertar(VK_WIN, ord("D")) = Win+D)."""
    user32 = ctypes.windll.user32
    extra = ESTENDIDA if estendida else 0
    for tecla in teclas:
        user32.keybd_event(tecla, 0, extra, 0)
    for tecla in reversed(teclas):
        user32.keybd_event(tecla, 0, extra | SOLTAR, 0)
