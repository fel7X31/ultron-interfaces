#!/usr/bin/env python3
"""Liga o Ultron com duas palmas e, com ele no ar, atende quando você chama ("Ultron").

Fica ouvindo o microfone. Quando ouve duas palmas seguidas, solta o microfone, liga o
server.py sem janela (se ele ainda não estiver no ar) e abre a esfera em tela cheia.
Desliga quando você manda por voz ("desliga") ou fecha a janela. Depois volta a ouvir.

Com o Ultron no ar, dizer "Ultron" faz ele ouvir o pedido (bipe, você fala, ele faz),
pelo reconhecimento de fala do Windows (ultron/voz/chamado.ps1), sem internet.
O Ctrl+Alt+V (segurar e falar) e o microfone da barra do topo também passam por aqui.

Rodar:           py palmas.py
Testar o nome:   py palmas.py --testar-chamado   (mostra cada "Ultron" que o Windows ouviu e com que certeza)
Calibrar:        py palmas.py --calibrar   (mostra o volume de cada som e não liga nada)
Desligar:        py palmas.py --desligar   (fecha o Ultron que as palmas ligaram)
Precisa de:      py -m pip install sounddevice numpy
"""
import functools
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import wave
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / ".estado"
ESTADO.mkdir(exist_ok=True)
if sys.stdout is None:
    sys.stdout = sys.stderr = open(ESTADO / "palmas.log", "a", encoding="utf-8", buffering=1)

import numpy as np
import sounddevice as sd

from ultron.voz.chamado import Chamado, FimDaFala


def porta_do_env():
    """A porta do servidor (ULTRON_PORTA no .env), ou 8790."""
    try:
        for linha in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            if linha.strip().startswith(("ULTRON_PORTA=", "JARVIS_PORTA=")):
                return int(linha.split("=", 1)[1].strip().strip("\"'"))
    except (FileNotFoundError, ValueError):
        pass
    return 8790


URL = f"http://localhost:{porta_do_env()}"
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
CHAMADO_ACEITA = ("High", "Medium", "Low")  # certeza do Windows pra valer (tire "Low" se ele ouvir sozinho)
CHAMADO_NOME_MAX_S = 2.0   # "Ultron" ou "Ei, Ultron" é curto: frase comprida que o Windows achou parecida não vale
CHAMADO_ESPERA_S = 5       # depois do bipe, quanto espera você começar a falar
CHAMADO_SILENCIO_S = 0.8   # quanto silêncio, depois de falar, encerra o pedido
CHAMADO_MAX_S = 20
FALANDO_NO_MAXIMO_S = 60   # sem o aviso de que a voz acabou, depois disso aceita o nome de novo

BLOCO_S = 0.01
SEM_AUDIO_S = 3
PID = ESTADO / "servidor.pid"
PID_TELA = ESTADO / "tela.pid"
LOG = ESTADO / "log.jsonl"
GRAVANDO = threading.Lock()   # um pedido gravado de cada vez (atalho, nome ou botão)
VOZ_DO_ULTRON = {"ate": 0.0}  # até quando a resposta dele pode estar tocando (o nome dito por ele não vale)


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


def saude():
    """O que o servidor diz de si, ou None se ele não está no ar."""
    try:
        with urllib.request.urlopen(URL + "/api/saude", timeout=1.5) as r:
            return json.load(r)
    except Exception:
        return None


def postar(caminho, dados, tipo="application/json", timeout=2):
    """POST pro servidor do Ultron. Devolve o erro, ou None se deu certo."""
    try:
        req = urllib.request.Request(URL + caminho, data=dados, headers={"Content-Type": tipo})
        urllib.request.urlopen(req, timeout=timeout).close()
    except Exception as erro:
        return erro


def avisar_tela(dados):
    """Conta pra tela do Ultron o que o atalho está fazendo (ouvindo, volume, parado)."""
    postar("/api/atalho", json.dumps(dados).encode(), timeout=0.5)


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


def eventos_novos(pos):
    """Os eventos que entraram no log.jsonl depois da posição pos, e a posição nova."""
    if not LOG.exists() or LOG.stat().st_size <= pos:
        return [], pos
    with open(LOG, encoding="utf-8", errors="replace") as f:
        f.seek(pos)
        linhas = f.read().splitlines()
        pos = f.tell()
    eventos = []
    for linha in linhas:
        try:
            eventos.append(json.loads(linha))
        except ValueError:
            pass
    return eventos, pos


def pediu_desligar(ev):
    """Você mandou desligar, ou ele respondeu "desligando"."""
    return ev.get("evento") == "turno" and bool(
        DESLIGAR_VOCE.search(ev.get("voce") or "") or DESLIGAR_RESPOSTA.search(ev.get("resposta") or ""))


def hora_de_desligar(eventos, desligar_em):
    """8 s depois do pedido de desligar, ou meio segundo depois que a resposta terminou de tocar."""
    for ev in eventos:
        if desligar_em is None and pediu_desligar(ev):
            print("Pedido de desligar.")
            desligar_em = time.time() + 8
        elif desligar_em and ev.get("evento") == "tela" and ev.get("tipo") == "voz_tocou":
            desligar_em = time.time() + 0.5
    return desligar_em


def acompanhar():
    """Espera o Ultron ser desligado (por voz, fechando a janela ou de fora) e, enquanto isso, atende quem chama."""
    pos = LOG.stat().st_size if LOG.exists() else 0
    desligar_em = ultima_tela = None
    chamado = Chamado(lambda *ouviu: em_paralelo(ao_ser_chamado, *ouviu))
    try:
        while True:
            time.sleep(0.5)
            s = saude()
            if s is None:
                return
            eventos, pos = eventos_novos(pos)
            desligar_em = hora_de_desligar(eventos, desligar_em)
            atender(eventos, s, chamado)
            if s.get("telas"):
                ultima_tela = time.time()
            if desligar_em and time.time() >= desligar_em:
                return desligar_ultron()
            if ultima_tela and time.time() - ultima_tela >= SEM_TELA_DESLIGA:
                print("A janela foi fechada.")
                return desligar_ultron()
    finally:
        chamado.desligar()


def em_paralelo(funcao, *args):
    threading.Thread(target=funcao, args=args, daemon=True).start()


def atender(eventos, s, chamado):
    """Liga o ouvido do nome (se a preferência da tela deixar), acompanha a voz do Ultron e o microfone da barra."""
    if s.get("chamado", True):
        chamado.ligar()
    else:
        chamado.desligar()
    for ev in eventos:
        if ev.get("evento") == "turno" and ev.get("resposta"):
            VOZ_DO_ULTRON["ate"] = time.time() + min(FALANDO_NO_MAXIMO_S, 2 + len(ev["resposta"]) / 12)
        elif ev.get("evento") == "tela" and ev.get("tipo") in ("voz_tocou", "voz_falhou"):
            VOZ_DO_ULTRON["ate"] = time.time() + 0.5
        elif ev.get("evento") == "chamar":
            em_paralelo(ao_ser_chamado, "botao", 1.0, 0.0)


def vale_o_nome(confianca, segundos):
    """O Windows ouviu o nome com certeza bastante e curto (não era uma frase comprida parecida)?"""
    return confianca in CHAMADO_ACEITA and segundos <= CHAMADO_NOME_MAX_S


def ao_ser_chamado(confianca, certeza, segundos):
    """Ouviu "Ultron" (ou o microfone da barra): bipe, grava o pedido até você parar de falar e manda pro Ultron."""
    pelo_botao = confianca == "botao"
    if not pelo_botao and not vale_o_nome(confianca, segundos):
        print(f"Ouvi algo como \"Ultron\" ({confianca} {certeza:.2f}, {segundos:.1f} s). Não valeu.")
        return
    s = saude()
    falando = time.time() < VOZ_DO_ULTRON["ate"]
    ocupado = not s or s.get("estado") != "parado" or falando
    if (ocupado and not pelo_botao) or not GRAVANDO.acquire(blocking=False):
        motivo = "falando" if falando else (s.get("estado") if s else "desligado")
        print(f"\"Ultron\" ignorado: ele está {motivo}.")
        return
    try:
        print(f"Chamado ({confianca} {certeza:.2f}). Ouvindo o pedido...")
        if pelo_botao:
            postar("/api/interromper", b"")
        mandar_fala(gravar_ate_o_silencio(), "Chamado")
    except Exception as erro:
        print(f"Chamado: não consegui gravar ({erro}).")
        avisar_tela({"estado": "cancelado"})
    finally:
        GRAVANDO.release()


def gravar_ate_o_silencio():
    """O pedido falado depois do bipe, até você ficar CHAMADO_SILENCIO_S quieto. None se não falou nada."""
    taxa, blocos, pedacos = taxa_do_microfone(), queue.Queue(), []
    bloco_s = 0.05
    fim = FimDaFala(CHAMADO_ESPERA_S, CHAMADO_SILENCIO_S)
    with sd.InputStream(samplerate=taxa, channels=1, dtype="float32", blocksize=int(taxa * bloco_s),
                        callback=lambda d, *_: blocos.put(d[:, 0].copy())):
        bipe(880)
        avisar_tela({"estado": "ouvindo"})
        situacao, inicio = "esperando", time.time()
        while situacao in ("esperando", "falando") and time.time() - inicio < CHAMADO_MAX_S:
            bloco = proximo_bloco(blocos)
            pedacos.append(bloco)
            situacao = fim.receber(float(np.sqrt(np.mean(bloco ** 2))), bloco_s)
            if len(pedacos) % 2 == 0:
                avisar_tela({"nivel": volume(bloco)})
    bipe(520)
    return None if situacao == "nada" else np.concatenate(pedacos)


def mandar_fala(audio, quem):
    """Manda o áudio gravado pro Ultron (ou cancela, se foi só silêncio)."""
    wav = para_wav(audio, taxa_do_microfone()) if audio is not None else None
    if not wav:
        avisar_tela({"estado": "cancelado"})
        return
    avisar_tela({"estado": "parado"})
    erro = postar("/api/audio", wav, tipo="audio/wav", timeout=10)
    if erro:
        print(f"{quem}: o servidor não aceitou o áudio ({erro}).")


def testar_chamado():
    """Mostra cada "Ultron" que o Windows reconhece e com que certeza, sem ligar nada. Ctrl+C pra sair."""
    def mostrar(confianca, certeza, segundos):
        aceito = "  >>> vale" if vale_o_nome(confianca, segundos) else "  (não vale)"
        print(f"  ouvi \"Ultron\": {confianca} ({certeza:.2f}), {segundos:.2f} s{aceito}")

    chamado = Chamado(mostrar)
    chamado.ligar()
    print("Diga \"Ultron\" algumas vezes, e também outras palavras e frases. Ctrl+C pra sair.")
    try:
        while chamado.ligado():
            time.sleep(0.5)
    finally:
        chamado.desligar()


def microfone_exclusivo(receber):
    """O microfone padrão no modo exclusivo do WASAPI (som cru, sem filtro do Windows)."""
    nome = sd.query_devices(kind="input")["name"][:25]
    wasapi = next(i for i, h in enumerate(sd.query_hostapis()) if "WASAPI" in h["name"])
    i, d = next((i, d) for i, d in enumerate(sd.query_devices())
                if d["hostapi"] == wasapi and d["max_input_channels"] > 0 and d["name"].startswith(nome))
    taxa = int(d["default_samplerate"])
    stream = sd.InputStream(device=i, samplerate=taxa, channels=d["max_input_channels"], dtype="float32",
                            blocksize=int(taxa * BLOCO_S), extra_settings=sd.WasapiSettings(exclusive=True),
                            callback=receber)
    return stream, taxa


def abrir_microfone(receber):
    """Abre o microfone padrão: tenta o modo exclusivo e, se não der, o normal."""
    if MODO_EXCLUSIVO and os.name == "nt":
        try:
            return (*microfone_exclusivo(receber), "exclusivo")
        except Exception as erro:
            print(f"Modo exclusivo não abriu ({erro!r}). Usando o modo normal.")
    taxa = taxa_do_microfone()
    stream = sd.InputStream(samplerate=taxa, blocksize=int(taxa * BLOCO_S), channels=1,
                            dtype="float32", callback=receber)
    return stream, taxa, "normal"


def proximo_bloco(blocos):
    """O próximo pedaço de áudio. Dá erro se o microfone parou (o Windows corta o stream ao suspender)."""
    try:
        return blocos.get(timeout=SEM_AUDIO_S)
    except queue.Empty:
        raise RuntimeError(f"sem áudio há {SEM_AUDIO_S} s") from None


def ouvir(calibrar=False):
    """Fica no microfone até ouvir duas palmas. Em modo calibrar, só mostra o volume e nunca retorna."""
    blocos = queue.Queue()

    def receber(dados, _frames, _tempo, _status):
        blocos.put(dados.copy())

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
        print(f"Microfone no modo {modo}. " + ("Ouvindo. Bata duas palmas pra ligar." if not calibrar else
              "Calibrando. Bata palmas, fale, faça barulho normal. Ctrl+C pra sair."))
        while True:
            bloco = np.max(np.abs(proximo_bloco(blocos)), axis=1)
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
                        return "Duas palmas!"
                else:
                    ultima, pico_ultima = inicio, pico_som
                inicio = None
            elif t - inicio > DURACAO_MAX:
                if calibrar:
                    print(f"  ignorado (longo): pico {pico_som:.2f}  fundo {fundo:.3f}")
                inicio, descartar = None, True


@functools.lru_cache(maxsize=1)
def taxa_do_microfone():
    return int(sd.query_devices(kind="input")["default_samplerate"])


def bipe(frequencia):
    """Bipe curto, sem travar a gravação."""
    if ATALHO_BIPE:
        import winsound
        threading.Thread(target=winsound.Beep, args=(frequencia, 70), daemon=True).start()


def volume(bloco):
    return min(1.0, float(np.sqrt(np.mean(bloco ** 2))) * 15)


def gravar_enquanto_segura():
    """O áudio enquanto o V estiver apertado (mais ATALHO_CAUDA_S no fim), ou None se foi curto demais."""
    import ctypes
    segurando = lambda: ctypes.windll.user32.GetAsyncKeyState(ATALHO_TECLA) & 0x8000
    pedacos = []
    with sd.InputStream(samplerate=taxa_do_microfone(), channels=1, dtype="float32", latency="low",
                        callback=lambda d, *_: pedacos.append(d[:, 0].copy())):
        limite = time.time() + 2
        while not pedacos and time.time() < limite:
            time.sleep(0.005)
        bipe(880)
        avisar_tela({"estado": "ouvindo"})
        inicio = time.time()
        while segurando() and time.time() - inicio < ATALHO_MAX_S:
            time.sleep(0.08)
            if pedacos:
                avisar_tela({"nivel": volume(pedacos[-1])})
        time.sleep(ATALHO_CAUDA_S)
    bipe(520)
    if time.time() - inicio < 0.35 or not pedacos:
        return None
    return np.concatenate(pedacos)


def para_wav(audio, taxa):
    """WAV mono de 16 kHz com o volume normalizado, ou None se for só silêncio."""
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


def ao_apertar_atalho():
    """Interrompe o Ultron, grava enquanto o V estiver apertado e manda a fala pra ele."""
    if not saude():
        print("Ctrl+Alt+V: o Ultron está desligado. Bata duas palmas antes.")
        return
    if not GRAVANDO.acquire(blocking=False):
        return
    try:
        postar("/api/interromper", b"")
        try:
            audio = gravar_enquanto_segura()
        except Exception as erro:
            print(f"Ctrl+Alt+V: não consegui gravar ({erro}).")
            audio = None
        mandar_fala(audio, "Ctrl+Alt+V")
    finally:
        GRAVANDO.release()


def atalho_global():
    """Registra Ctrl+Alt+V no Windows e chama ao_apertar_atalho() a cada aperto."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312
    if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ATALHO_TECLA):
        print("Não consegui registrar o Ctrl+Alt+V (outro programa já usa esse atalho).")
        return
    print("Atalho Ctrl+Alt+V pronto.")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            ao_apertar_atalho()


def main():
    if "--desligar" in sys.argv:
        return desligar_ultron()
    if "--testar-chamado" in sys.argv:
        try:
            testar_chamado()
        except KeyboardInterrupt:
            pass
        return
    if "--calibrar" in sys.argv:
        try:
            ouvir(calibrar=True)
        except KeyboardInterrupt:
            pass
        return
    if ATALHO_GLOBAL and os.name == "nt":
        threading.Thread(target=atalho_global, daemon=True).start()
    while True:
        if saude():
            acompanhar()
            continue
        try:
            print(ouvir())
        except Exception as erro:
            print(f"Microfone indisponível ({erro}). Tentando de novo em 5 s.")
            time.sleep(5)
            continue
        ligar_ultron()
        acompanhar()
        print("O Ultron foi desligado. Voltando a ouvir.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
