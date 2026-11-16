"""Ouvir o Ultron ser chamado pelo nome ("Ultron!"), pelo reconhecimento de fala do Windows (chamado.ps1).

O palmas.py liga enquanto o Ultron está no ar: cada vez que o Windows reconhece o nome, chama
ao_ouvir(confiança, certeza, segundos). Roda no PC, sem internet. Fora do Windows, não faz nada.
"""
import os
import subprocess
import threading
import time
from pathlib import Path

SCRIPT = Path(__file__).with_name("chamado.ps1")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ESPERA_DEPOIS_DE_FALHAR_S = 60


class Chamado:
    def __init__(self, ao_ouvir, ao_avisar=print):
        self.ao_ouvir, self.ao_avisar = ao_ouvir, ao_avisar
        self.processo = None
        self.falhou_em = 0.0

    def ligar(self):
        """Começa a ouvir (se já não estiver ouvindo e não tiver falhado agora há pouco)."""
        if os.name != "nt" or self.ligado() or time.time() - self.falhou_em < ESPERA_DEPOIS_DE_FALHAR_S:
            return
        self.processo = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-Dono", str(os.getpid())],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", creationflags=SEM_JANELA)
        threading.Thread(target=self._ler, args=(self.processo,), daemon=True).start()

    def desligar(self):
        if self.ligado():
            self.processo.kill()
        self.processo = None

    def ligado(self):
        return bool(self.processo and self.processo.poll() is None)

    def _ler(self, processo):
        for linha in processo.stdout:
            self.tratar(linha)
        if processo is self.processo:  # o script parou sem ninguém mandar
            self.falhou_em = time.time()

    def tratar(self, linha):
        partes = linha.split()
        if partes[:1] == ["ultron"] and len(partes) >= 4:
            self.ao_ouvir(partes[1], float(partes[2]), float(partes[3]))
        elif partes[:1] == ["pronto"]:
            self.ao_avisar("Ouvindo o nome \"Ultron\" (reconhecimento de fala do Windows).")
        elif partes:
            self.ao_avisar("Chamado: " + linha.strip())


class FimDaFala:
    """Depois do bipe: decide, bloco a bloco, se você ainda está falando. Compara o volume com o ruído de fundo
    (o mais baixo ouvido até ali), então serve pra microfone alto ou baixo."""
    IGNORAR_S = 0.3      # o começo tem o bipe: só mede o fundo
    ACIMA_DO_FUNDO = 3.0
    MINIMO = 0.0005      # abaixo disso é silêncio, qualquer que seja o fundo
    VOZ_MINIMA_S = 0.25  # um estalo não conta como fala

    def __init__(self, espera_s, silencio_s):
        self.espera_s, self.silencio_s = espera_s, silencio_s
        self.fundo, self.tempo, self.voz_s, self.quieto_s = None, 0.0, 0.0, 0.0

    def receber(self, volume, segundos):
        """volume: o RMS do bloco. Devolve "esperando", "falando", "acabou" ou "nada" (não falou nada a tempo)."""
        self.tempo += segundos
        if self.fundo is None or self.tempo <= self.IGNORAR_S:
            self.fundo = volume if self.fundo is None else min(self.fundo, volume)
            return "esperando"
        if volume > max(self.fundo * self.ACIMA_DO_FUNDO, self.MINIMO):
            self.voz_s += segundos
            self.quieto_s = 0.0
        else:
            self.fundo = min(volume, self.fundo * 1.005)  # o fundo sobe devagar se o ambiente ficar mais barulhento
            self.quieto_s += segundos
        if self.voz_s < self.VOZ_MINIMA_S:
            return "nada" if self.tempo > self.espera_s else "esperando"
        return "acabou" if self.quieto_s >= self.silencio_s else "falando"
