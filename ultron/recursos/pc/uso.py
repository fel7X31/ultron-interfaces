"""Uso do PC agora: processador, memória, disco, placa de vídeo e bateria."""
import ctypes
import shutil
import subprocess
import time
from ctypes import wintypes

GB = 1024 ** 3
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ANTERIOR = {"processador": None}  # (ocioso, total) da leitura anterior: o uso é a diferença entre as duas


class _Memoria(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _Energia(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


def _em_numero(tempo):
    return (tempo.dwHighDateTime << 32) | tempo.dwLowDateTime


def _tempos_do_processador():
    """(tempo ocioso, tempo total) desde que o PC ligou. O tempo do núcleo já inclui o ocioso."""
    ocioso, nucleo, usuario = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(ocioso), ctypes.byref(nucleo), ctypes.byref(usuario))
    return _em_numero(ocioso), _em_numero(nucleo) + _em_numero(usuario)


def processador():
    """% de uso do processador desde a leitura anterior (na primeira, mede por um instante)."""
    if _ANTERIOR["processador"] is None:
        _ANTERIOR["processador"] = _tempos_do_processador()
        time.sleep(0.2)
    ocioso_antes, total_antes = _ANTERIOR["processador"]
    ocioso, total = _tempos_do_processador()
    _ANTERIOR["processador"] = (ocioso, total)
    passou = total - total_antes
    return round(100 * (1 - (ocioso - ocioso_antes) / passou)) if passou else 0


def memoria():
    m = _Memoria(dwLength=ctypes.sizeof(_Memoria))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    usada = m.ullTotalPhys - m.ullAvailPhys
    return {"pct": m.dwMemoryLoad, "usada_gb": round(usada / GB, 1), "total_gb": round(m.ullTotalPhys / GB, 1)}


def disco(unidade="C:\\"):
    d = shutil.disk_usage(unidade)
    return {"pct": round(100 * d.used / d.total), "livre_gb": round(d.free / GB), "total_gb": round(d.total / GB)}


def placa_de_video():
    """Uso, temperatura e memória da placa NVIDIA (pelo nvidia-smi), ou None se não tiver."""
    programa = shutil.which("nvidia-smi")
    if not programa:
        return None
    try:
        r = subprocess.run([programa, "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
                           creationflags=SEM_JANELA)
        uso, temperatura, usada, total = (float(x) for x in r.stdout.splitlines()[0].split(","))
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None
    return {"pct": round(uso), "temperatura": round(temperatura), "memoria_pct": round(100 * usada / total)}


def bateria():
    """% e se está carregando, ou None num PC sem bateria."""
    e = _Energia()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(e))
    if e.BatteryFlag & 128 or e.BatteryLifePercent == 255:
        return None
    return {"pct": e.BatteryLifePercent, "carregando": e.ACLineStatus == 1}


def uso():
    """Tudo junto, pro painel da barra."""
    return {"processador": processador(), "memoria": memoria(), "disco": disco(),
            "placa_de_video": placa_de_video(), "bateria": bateria()}
