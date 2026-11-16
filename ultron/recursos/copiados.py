"""Copiados: os últimos textos que você copiou (Ctrl+C), pra copiar de novo pela barra.

Só texto, só na memória do Ultron (some ao desligar) e nunca vai pro disco nem pro Claude. Respeita os gerenciadores
de senha: o que eles marcam pra ficar fora do histórico do Windows fica fora daqui também.
"""
import ctypes
import hashlib
import os
import threading
import time

from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log_erro

LIMITE = 30
MAIOR_TEXTO = 20000
INTERVALO_S = 0.7
TEXTO = 13  # CF_UNICODETEXT
MOVEL = 0x0002  # GMEM_MOVEABLE
ITENS = []  # [{id, texto, quando}], o mais novo primeiro
TRAVA = threading.Lock()

if os.name == "nt":
    from ctypes import wintypes
    user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]


def listar():
    return {"itens": list(ITENS)}


def guardar(texto):
    """Põe o texto no topo da lista (se já estava, só sobe). Devolve True se entrou algo."""
    if not texto or not texto.strip() or len(texto) > MAIOR_TEXTO:
        return False
    id_texto = hashlib.sha1(texto.encode("utf-8", "replace")).hexdigest()[:10]
    with TRAVA:
        ITENS[:] = [{"id": id_texto, "texto": texto, "quando": time.strftime("%H:%M")}] + \
                   [i for i in ITENS if i["id"] != id_texto][:LIMITE - 1]
    EVENTOS.emitir({"tipo": "copiados"})
    return True


def apagar(id_texto=""):
    """Tira um item (ou todos, sem id)."""
    with TRAVA:
        ITENS[:] = [i for i in ITENS if id_texto and i["id"] != id_texto]
    EVENTOS.emitir({"tipo": "copiados"})


def copiar(id_texto):
    """Põe um item da lista de volta na área de transferência. ValueError se ele não existe mais."""
    item = next((i for i in ITENS if i["id"] == id_texto), None)
    if not item:
        raise ValueError("Esse texto não está mais na lista.")
    _escrever(item["texto"])
    return item


def vigiar():
    """Fica olhando a área de transferência (só no Windows) e guarda cada texto novo. Roda numa thread."""
    if os.name != "nt":
        return
    ultima = user32.GetClipboardSequenceNumber()
    while True:
        time.sleep(INTERVALO_S)
        numero = user32.GetClipboardSequenceNumber()
        if numero == ultima:
            continue
        ultima = numero
        try:
            guardar(_ler())
        except Exception as erro:
            log_erro("copiados_falhou", erro)


def _abrir():
    for _ in range(10):  # outro programa pode estar com ela aberta
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def _fora_do_historico():
    """O programa que copiou pediu pra ficar fora do histórico (gerenciador de senha, por exemplo)?"""
    if user32.IsClipboardFormatAvailable(user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")):
        return True
    formato = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
    if not user32.IsClipboardFormatAvailable(formato):
        return False
    dados = user32.GetClipboardData(formato)
    ponteiro = kernel32.GlobalLock(dados) if dados else None
    if not ponteiro:
        return True
    try:
        return ctypes.c_uint32.from_address(ponteiro).value == 0
    finally:
        kernel32.GlobalUnlock(dados)


def _ler():
    if not user32.IsClipboardFormatAvailable(TEXTO) or not _abrir():
        return None
    try:
        if _fora_do_historico():
            return None
        dados = user32.GetClipboardData(TEXTO)
        ponteiro = kernel32.GlobalLock(dados) if dados else None
        if not ponteiro:
            return None
        try:
            return ctypes.wstring_at(ponteiro)
        finally:
            kernel32.GlobalUnlock(dados)
    finally:
        user32.CloseClipboard()


def _escrever(texto):
    buffer = ctypes.create_unicode_buffer(texto)
    memoria = kernel32.GlobalAlloc(MOVEL, ctypes.sizeof(buffer))
    ponteiro = kernel32.GlobalLock(memoria)
    ctypes.memmove(ponteiro, buffer, ctypes.sizeof(buffer))
    kernel32.GlobalUnlock(memoria)
    if not _abrir():
        kernel32.GlobalFree(memoria)
        raise ValueError("A área de transferência está ocupada por outro programa. Tente de novo.")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(TEXTO, memoria):
            kernel32.GlobalFree(memoria)
            raise ValueError("Não consegui copiar.")
    finally:
        user32.CloseClipboard()
