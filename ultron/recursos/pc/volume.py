"""Volume do Windows (o mesmo do ícone de som da barra de tarefas), pela interface de áudio do sistema.

Fala com o Windows pelo COM, direto com ctypes: cada método é chamado pelo número dele na interface
(a ordem vem da documentação da Microsoft: IMMDeviceEnumerator, IMMDevice e IAudioEndpointVolume).
"""
import ctypes
from contextlib import contextmanager
from ctypes import POINTER, byref, c_float, c_int, c_ulong, c_ushort, c_void_p, wintypes

ENUMERADOR = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
INTERFACE_ENUMERADOR = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
INTERFACE_VOLUME = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
TODOS_OS_CONTEXTOS = 0x17
SAIDA_DE_SOM, MULTIMIDIA = 0, 1
LIBERAR, PEGAR_SAIDA_PADRAO, ATIVAR = 2, 4, 3
MUDAR_NIVEL, LER_NIVEL, MUDAR_MUDO, LER_MUDO = 7, 9, 14, 15


class _Guid(ctypes.Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", ctypes.c_ubyte * 8)]


def _guid(texto):
    guid = _Guid()
    ctypes.oledll.ole32.CLSIDFromString(texto, byref(guid))
    return guid


def _chamar(objeto, indice, *argumentos):
    """Chama o método número `indice` de um objeto COM com esses argumentos."""
    tabela = ctypes.cast(objeto, POINTER(POINTER(c_void_p))).contents
    metodo = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *(type(a) for a in argumentos))(tabela[indice])
    return metodo(objeto, *argumentos)


@contextmanager
def _controle():
    """O controle de volume da saída de som padrão (abre e fecha o COM nesta thread)."""
    ctypes.windll.ole32.CoInitialize(None)
    abertos = []
    try:
        enumerador, dispositivo, controle = c_void_p(), c_void_p(), c_void_p()
        ctypes.oledll.ole32.CoCreateInstance(byref(_guid(ENUMERADOR)), None, TODOS_OS_CONTEXTOS,
                                             byref(_guid(INTERFACE_ENUMERADOR)), byref(enumerador))
        abertos.append(enumerador)
        _chamar(enumerador, PEGAR_SAIDA_PADRAO, c_int(SAIDA_DE_SOM), c_int(MULTIMIDIA), ctypes.pointer(dispositivo))
        abertos.append(dispositivo)
        _chamar(dispositivo, ATIVAR, ctypes.pointer(_guid(INTERFACE_VOLUME)), wintypes.DWORD(TODOS_OS_CONTEXTOS),
                c_void_p(None), ctypes.pointer(controle))
        abertos.append(controle)
        yield controle
    finally:
        for objeto in reversed(abertos):
            _chamar(objeto, LIBERAR)
        ctypes.windll.ole32.CoUninitialize()


def ler():
    """{"nivel": 0 a 100, "mudo": True ou False}"""
    nivel, mudo = c_float(), wintypes.BOOL()
    with _controle() as controle:
        _chamar(controle, LER_NIVEL, ctypes.pointer(nivel))
        _chamar(controle, LER_MUDO, ctypes.pointer(mudo))
    return {"nivel": round(nivel.value * 100), "mudo": bool(mudo.value)}


def mudar(nivel):
    """Põe o volume em `nivel` (0 a 100) e tira do mudo. Devolve como ficou."""
    nivel = max(0, min(100, int(nivel)))
    with _controle() as controle:
        _chamar(controle, MUDAR_NIVEL, c_float(nivel / 100), c_void_p(None))
        _chamar(controle, MUDAR_MUDO, wintypes.BOOL(False), c_void_p(None))
    return ler()


def somar(passo):
    """Sobe (passo positivo) ou desce o volume. Devolve como ficou."""
    return mudar(ler()["nivel"] + passo)


def silenciar(mudo=True):
    """Liga ou desliga o mudo, sem mexer no nível. Devolve como ficou."""
    with _controle() as controle:
        _chamar(controle, MUDAR_MUDO, wintypes.BOOL(mudo), c_void_p(None))
    return ler()
