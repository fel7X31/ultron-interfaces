#!/usr/bin/env python3
"""Liga o Ultron com duas palmas.

Fica ouvindo o microfone. Quando ouve duas palmas seguidas, solta o microfone,
liga o server.py sem janela (se ele ainda não estiver no ar) e abre a esfera
em tela cheia. Desliga quando você manda por voz ("desliga") ou fecha a janela.
Depois volta a ouvir as palmas.

Rodar:           py palmas.py
Calibrar:        py palmas.py --calibrar   (mostra o volume de cada som e não liga nada)
Desligar:        py palmas.py --desligar   (fecha o Ultron que as palmas ligaram)
Precisa de:      py -m pip install sounddevice numpy
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / ".estado"
ESTADO.mkdir(exist_ok=True)
if sys.stdout is None:
    sys.stdout = sys.stderr = open(ESTADO / "palmas.log", "a", encoding="utf-8", buffering=1)

import numpy as np
import sounddevice as sd

LIMIAR = 0.08
PALMA_FORTE = 0.22
RAZAO_FUNDO = 6.0
DURACAO_MAX = 0.15
INTERVALO_MIN = 0.1
INTERVALO_MAX = 1.2
MODO_EXCLUSIVO = True
TELA_CHEIA = True
NOME = r"(ultr\w*|altr\w*|outro|oculto|jarvis)"
DESLIGAR_VOCE = re.compile(
    rf"^\W*(pode\s+)?deslig\w*\W*$|\b{NOME}\W+(pode\s+)?(se\s+)?deslig\w*"
    rf"|\bdeslig\w*\s+(o\s+|a\s+)?({NOME}|sistema|tudo)\b|\bse\s+deslig\w*\b",
    re.I)
DESLIGAR_RESPOSTA = re.compile(r"^\W*desligando\b", re.I)
SEM_TELA_DESLIGA = 3
ATALHO_GLOBAL = True
ATALHO_TECLA = 0x56
ATALHO_BIPE = True
ATALHO_MAX_S = 30
ATALHO_CAUDA_S = 0.25

BLOCO_S = 0.01
PID = ESTADO / "servidor.pid"
PID_TELA = ESTADO / "tela.pid"
LOG = ESTADO / "log.jsonl"


def matar(arquivo_pid):
    try:
        pid = int(arquivo_pid.read_text().strip())
    except (FileNotFoundError, ValueError):
        return False
    arquivo_pid.unlink(missing_ok=True)
    if os.name == "nt":
        r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0
    try:
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def desligar_ultron():
    """Fecha o servidor e a janela que o palmas.py abriu."""
    matar(PID_TELA)
    print("Ultron desligado." if matar(PID) else "Não achei um Ultron ligado pelas palmas.")


def abrir_microfone(receber):
    """Abre o microfone padrão. Tenta o modo exclusivo (cru) antes do normal."""
    padrao = sd.query_devices(kind="input")
    if MODO_EXCLUSIVO and os.name == "nt":
        try:
            wasapi = next(i for i, h in enumerate(sd.query_hostapis()) if "WASAPI" in h["name"])
            for i, d in enumerate(sd.query_devices()):
                if (d["hostapi"] == wasapi and d["max_input_channels"] > 0
                        and d["name"].startswith(padrao["name"][:25])):
                    taxa = int(d["default_samplerate"])
                    stream = sd.InputStream(
                        device=i, samplerate=taxa, channels=d["max_input_channels"], dtype="float32",
                        blocksize=int(taxa * BLOCO_S), extra_settings=sd.WasapiSettings(exclusive=True),
                        callback=receber)
                    return stream, taxa, "exclusivo"
        except Exception as erro:
            print(f"Modo exclusivo não abriu ({erro}). Usando o modo normal.")
    taxa = int(padrao["default_samplerate"])
    stream = sd.InputStream(samplerate=taxa, blocksize=int(taxa * BLOCO_S), channels=1,
                            dtype="float32", callback=receber)
    return stream, taxa, "normal"


def porta():
    try:
        for linha in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            if linha.strip().startswith(("ULTRON_PORTA=", "JARVIS_PORTA=")):
                return int(linha.split("=", 1)[1].strip().strip('"').strip("'"))
    except (FileNotFoundError, ValueError):
        pass
    return 8790


URL = f"http://localhost:{porta()}"


def saude():
    """O que o servidor diz de si, ou None se ele não está no ar."""
    try:
        with urllib.request.urlopen(URL + "/api/saude", timeout=1.5) as r:
            return json.load(r)
    except Exception:
        return None


def navegador():
    """Edge ou Chrome, pra abrir a esfera numa janela própria."""
    candidatos = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return shutil.which("msedge") or shutil.which("chrome")


def abrir_tela():
    exe = navegador() if TELA_CHEIA else None
    if not exe:
        webbrowser.open(URL)
        return
    perfil = ESTADO / "navegador"
    proc = subprocess.Popen([exe, f"--app={URL}", "--start-fullscreen", f"--user-data-dir={perfil}",
                             "--no-first-run", "--no-default-browser-check"])
    PID_TELA.write_text(str(proc.pid))


def ligar_ultron():
    if saude():
        print("O Ultron já está no ar. Só vou abrir a tela.")
    else:
        print("Ligando o Ultron...")
        log = open(ESTADO / "servidor.log", "a", encoding="utf-8")
        extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        py = Path(sys.executable)
        if py.name.lower() == "pythonw.exe" and (py.parent / "python.exe").exists():
            py = py.parent / "python.exe"
        proc = subprocess.Popen([str(py), "-u", str(RAIZ / "server.py"), "--sem-abrir"], cwd=str(RAIZ),
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **extra)
        PID.write_text(str(proc.pid))
        limite = time.time() + 30
        while not saude():
            if time.time() > limite:
                print("O servidor não respondeu em 30 segundos. Veja .estado/servidor.log.")
                return
            time.sleep(0.3)
    abrir_tela()


def acompanhar():
    """Espera o Ultron ser desligado: por voz, fechando a janela ou de fora."""
    pos = LOG.stat().st_size if LOG.exists() else 0
    desligar_em = None
    sem_tela_desde = None
    viu_tela = False
    while True:
        time.sleep(1)
        s = saude()
        if s is None:
            return
        if LOG.exists() and LOG.stat().st_size > pos:
            with open(LOG, encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                novas = f.read()
                pos = f.tell()
            for linha in novas.splitlines():
                try:
                    ev = json.loads(linha)
                except ValueError:
                    continue
                if ev.get("evento") == "turno" and desligar_em is None and (
                        DESLIGAR_VOCE.search(ev.get("voce") or "")
                        or DESLIGAR_RESPOSTA.search(ev.get("resposta") or "")):
                    print("Pedido de desligar.")
                    desligar_em = time.time() + 8
                elif desligar_em and ev.get("evento") == "tela" and ev.get("tipo") == "voz_tocou":
                    desligar_em = time.time() + 0.5
        if desligar_em and time.time() >= desligar_em:
            desligar_ultron()
            return
        telas = s.get("telas", 0)
        if telas:
            viu_tela, sem_tela_desde = True, None
        elif viu_tela:
            sem_tela_desde = sem_tela_desde or time.time()
            if time.time() - sem_tela_desde >= SEM_TELA_DESLIGA:
                print("A janela foi fechada.")
                desligar_ultron()
                return


def ouvir(calibrar=False):
    """Fica no microfone até ouvir duas palmas. Em modo calibrar, nunca retorna."""
    blocos = queue.Queue()

    def receber(dados, _frames, _tempo, _status):
        blocos.put(np.max(np.abs(dados), axis=1))

    fundo = 0.01
    inicio = None
    pico_som = 0.0
    descartar = False
    ultima = None
    pico_ultima = 0.0
    t = 0.0
    janela_inicio, janela_pico = 0.0, 0.0

    stream, taxa, modo = abrir_microfone(receber)
    with stream:
        print(f"Microfone no modo {modo}. " + ("Ouvindo. Bata duas palmas." if not calibrar else
              "Calibrando. Bata palmas, fale, faça barulho normal. Ctrl+C pra sair."))
        while True:
            bloco = blocos.get()
            t += len(bloco) / taxa
            pico = float(np.max(bloco))
            rms = float(np.sqrt(np.mean(bloco ** 2)))
            if calibrar:
                janela_pico = max(janela_pico, pico)
                if t - janela_inicio >= 0.25:
                    if janela_pico >= 0.03:
                        print(f"{t:7.2f} s  volume {janela_pico:.2f}  " + "#" * int(janela_pico * 50))
                    janela_inicio, janela_pico = t, 0.0

            if inicio is None:
                if pico >= LIMIAR and pico >= fundo * RAZAO_FUNDO and not descartar:
                    inicio, pico_som = t, pico
                else:
                    fundo = 0.98 * fundo + 0.02 * max(rms, 0.001)
                    if descartar and pico < LIMIAR * 0.3:
                        descartar = False
                continue

            pico_som = max(pico_som, pico)
            if pico < LIMIAR * 0.3:
                duracao = t - inicio
                if calibrar:
                    print(f"  palma? pico {pico_som:.2f}  fundo {fundo:.3f}  duração {duracao:.2f} s")
                if (ultima is not None and INTERVALO_MIN <= inicio - ultima <= INTERVALO_MAX
                        and max(pico_ultima, pico_som) >= PALMA_FORTE):
                    if calibrar:
                        print(f"  >>> DUAS PALMAS ({inicio - ultima:.2f} s entre elas)")
                        ultima = None
                    else:
                        return
                else:
                    ultima, pico_ultima = inicio, pico_som
                inicio = None
            elif t - inicio > DURACAO_MAX:
                if calibrar:
                    print(f"  ignorado (longo): pico {pico_som:.2f}  fundo {fundo:.3f}")
                inicio, descartar = None, True


TAXA_MIC = None


def avisar_tela(dados):
    """Conta pra tela do Ultron o que o atalho está fazendo (ouvindo, volume, parado)."""
    try:
        req = urllib.request.Request(URL + "/api/atalho", data=json.dumps(dados).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=0.5).close()
    except Exception:
        pass


def gravar_enquanto_segura(bipe):
    """Grava do microfone (modo normal) enquanto o V estiver apertado. Devolve um WAV.

    O bipe agudo só toca depois que o microfone já está gravando (antes, o começo da
    frase se perdia). Depois de soltar, grava mais ATALHO_CAUDA_S pra não cortar o fim.
    """
    import ctypes, io, wave
    segura = lambda: ctypes.windll.user32.GetAsyncKeyState(ATALHO_TECLA) & 0x8000
    global TAXA_MIC
    if not TAXA_MIC:
        TAXA_MIC = int(sd.query_devices(kind="input")["default_samplerate"])
    taxa = TAXA_MIC
    pedacos = []
    stream = sd.InputStream(samplerate=taxa, channels=1, dtype="float32", latency="low",
                            callback=lambda d, *_: pedacos.append(d[:, 0].copy()))
    with stream:
        limite = time.time() + 2
        while not pedacos and time.time() < limite:
            time.sleep(0.005)
        bipe(880)
        avisar_tela({"estado": "ouvindo"})
        inicio = time.time()
        ultimo_nivel = 0.0
        while segura() and time.time() - inicio < ATALHO_MAX_S:
            time.sleep(0.01)
            if time.time() - ultimo_nivel >= 0.08:
                ultimo_nivel = time.time()
                bloco = pedacos[-1]
                avisar_tela({"nivel": min(1.0, float(np.sqrt(np.mean(bloco ** 2))) * 15)})
        time.sleep(ATALHO_CAUDA_S)
    bipe(520)
    duracao = time.time() - inicio
    if duracao < 0.35 or not pedacos:
        return None
    audio = np.concatenate(pedacos)
    pico = float(np.max(np.abs(audio)))
    if pico < 0.005:
        return None
    audio = audio * (0.9 / pico)
    if taxa > 16000:
        n = int(len(audio) * 16000 / taxa)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
        taxa = 16000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def atalho_global():
    """Registra Ctrl+Alt+V no Windows e, a cada aperto, grava e manda a fala pro Ultron."""
    import ctypes
    from ctypes import wintypes
    import threading
    import winsound
    user32 = ctypes.windll.user32
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312
    if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ATALHO_TECLA):
        print("Não consegui registrar o Ctrl+Alt+V (outro programa já usa esse atalho).")
        return
    print("Atalho Ctrl+Alt+V pronto.")
    bipe = lambda f: threading.Thread(target=winsound.Beep, args=(f, 70), daemon=True).start() if ATALHO_BIPE else None
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message != WM_HOTKEY:
            continue
        if not saude():
            print("Ctrl+Alt+V: o Ultron está desligado. Bata duas palmas antes.")
            continue
        try:
            urllib.request.urlopen(urllib.request.Request(URL + "/api/interromper", data=b"", method="POST"), timeout=2)
        except Exception:
            pass
        try:
            wav = gravar_enquanto_segura(bipe)
        except Exception as erro:
            print(f"Ctrl+Alt+V: não consegui gravar ({erro}).")
            avisar_tela({"estado": "cancelado"})
            continue
        if not wav:
            avisar_tela({"estado": "cancelado"})
            continue
        avisar_tela({"estado": "parado"})
        try:
            req = urllib.request.Request(URL + "/api/audio", data=wav, headers={"Content-Type": "audio/wav"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as erro:
            print(f"Ctrl+Alt+V: o servidor não aceitou o áudio ({erro}).")


def main():
    if "--desligar" in sys.argv:
        return desligar_ultron()
    if "--calibrar" in sys.argv:
        try:
            ouvir(calibrar=True)
        except KeyboardInterrupt:
            pass
        return
    if ATALHO_GLOBAL and os.name == "nt":
        import threading
        threading.Thread(target=atalho_global, daemon=True).start()
    while True:
        if saude():
            acompanhar()
            continue
        try:
            ouvir()
        except Exception as erro:
            print(f"Microfone indisponível ({erro}). Tentando de novo em 5 s.")
            time.sleep(5)
            continue
        print("Duas palmas!")
        ligar_ultron()
        acompanhar()
        print("O Ultron foi desligado. Voltando a ouvir.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
