"""Os programas instalados, pelo nome que aparece no Windows, pra abrir pelo nome falado ("abre o rocket league").

Junta os atalhos do menu Iniciar e da área de trabalho (os jogos da Steam e da Epic ficam lá) e os apps do menu
Iniciar que o Windows lista (os da loja também: Paint, Calculadora...). Acha pelo nome mais parecido com o falado.
O app.py monta a lista ao ligar; ela só é refeita quando você pede um programa que não está nela.
"""
import ctypes
import difflib
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from ...nucleo.texto import normalizar

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PASTAS = (0x02, 0x17, 0x10, 0x19)  # menu Iniciar (seu e de todos) e área de trabalho (sua e de todos)
NAO_E_PROGRAMA = re.compile(r"\b(uninstall\w*|desinstal\w*|readme|leia ?me|help|ajuda|manual|website|site|suporte|"
                            r"support|license|licenca|release notes)\b")
APELIDOS = {"fifa": "ea sports fc"}  # nome falado -> pedaço do nome no Windows
EPIC = "Epic/EpicGamesLauncher/Data/Manifests"  # dentro do ProgramData
_GUARDADO = {"lista": []}
_TRAVA = threading.Lock()


def catalogo(de_novo=False):
    """[{"nome", "como"}] dos programas instalados. "como" é um atalho (.lnk ou .url) ou shell:AppsFolder\\<id>."""
    with _TRAVA:
        if de_novo or not _GUARDADO["lista"]:
            _GUARDADO["lista"] = _atalhos() + _apps_do_iniciar() + _jogos_da_epic() + _jogos_da_steam()
        return _GUARDADO["lista"]


def guardado():
    """A lista já montada (vazia se ainda não montou), pra consultar sem esperar."""
    return _GUARDADO["lista"]


def achar(nome, lista=None):
    """O programa com o nome mais parecido com o falado, ou None."""
    falado = " ".join(normalizar(nome))
    falado = APELIDOS.get(falado, falado)
    if not falado:
        return None
    nomes = {}
    for app in lista if lista is not None else catalogo():
        chave = " ".join(normalizar(app["nome"]))
        if chave and not NAO_E_PROGRAMA.search(chave):
            nomes.setdefault(chave, app)
    if falado in nomes:
        return nomes[falado]
    palavras = falado.split()
    com_tudo = [n for n in nomes if all(p in n.split() for p in palavras)]
    if com_tudo:
        return nomes[min(com_tudo, key=len)]  # o mais curto é o mais certeiro ("steam" e não "steam vr")
    parecido = difflib.get_close_matches(falado, list(nomes), n=1, cutoff=0.8)
    return nomes[parecido[0]] if parecido else None


def abrir(app):
    if app["como"].startswith("shell:"):
        subprocess.Popen(["explorer.exe", app["como"]], creationflags=SEM_JANELA)
    else:
        os.startfile(app["como"])  # atalho, ou link do launcher (com.epicgames.launcher://, steam://)


def _jogos_da_epic():
    """Os jogos instalados pela Epic (o launcher guarda um .item por jogo), abertos pelo link do launcher."""
    lista = []
    for arquivo in (Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / EPIC).glob("*.item"):
        try:
            jogo = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if jogo.get("DisplayName") and jogo.get("AppName"):
            codigo = f"{jogo.get('CatalogNamespace', '')}%3A{jogo.get('CatalogItemId', '')}%3A{jogo['AppName']}"
            lista.append({"nome": jogo["DisplayName"],
                          "como": f"com.epicgames.launcher://apps/{codigo}?action=launch&silent=true"})
    return lista


def _jogos_da_steam():
    """Os jogos instalados pela Steam (um appmanifest por jogo, em cada biblioteca), abertos pelo steam://."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as chave:
            steam = Path(winreg.QueryValueEx(chave, "SteamPath")[0])
        bibliotecas = (steam / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
    except (ImportError, OSError):
        return []
    pastas = {steam} | {Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', bibliotecas)}
    lista = []
    for pasta in pastas:
        for manifesto in (pasta / "steamapps").glob("appmanifest_*.acf"):
            texto = manifesto.read_text(encoding="utf-8", errors="replace")
            nome, codigo = re.search(r'"name"\s+"([^"]+)"', texto), re.search(r'"appid"\s+"(\d+)"', texto)
            if nome and codigo:
                lista.append({"nome": nome.group(1), "como": f"steam://rungameid/{codigo.group(1)}"})
    return lista


def _atalhos():
    lista = []
    for pasta in filter(None, map(_pasta_do_windows, PASTAS)):
        for arquivo in Path(pasta).rglob("*"):
            if arquivo.suffix.lower() in (".lnk", ".url"):
                lista.append({"nome": arquivo.stem, "como": str(arquivo)})
    return lista


def _apps_do_iniciar():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                            "Get-StartApps | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", timeout=20, creationflags=SEM_JANELA)
        apps = json.loads(r.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    apps = apps if isinstance(apps, list) else [apps]
    return [{"nome": a["Name"], "como": "shell:AppsFolder\\" + a["AppID"]} for a in apps if a.get("Name") and a.get("AppID")]


def _pasta_do_windows(codigo):
    if os.name != "nt":
        return None
    caminho = ctypes.create_unicode_buffer(260)
    return caminho.value if ctypes.windll.shell32.SHGetFolderPathW(None, codigo, None, 0, caminho) == 0 else None
