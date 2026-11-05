"""Eventos pra tela (Server-Sent Events). Qualquer parte do backend avisa a tela com EVENTOS.emitir({...})."""
import queue
import threading


class Eventos:
    def __init__(self):
        self.ouvintes = []
        self.lock = threading.Lock()
        self.ultimo_estado = {"tipo": "estado", "estado": "iniciando"}

    def emitir(self, evento):
        if evento.get("tipo") == "estado":
            self.ultimo_estado = evento
        with self.lock:
            for q in list(self.ouvintes):
                q.put(evento)

    def estado(self, nome):
        """Atalho: muda o estado da esfera (parado, pensando, transcrevendo...)."""
        self.emitir({"tipo": "estado", "estado": nome})

    def aviso(self, texto):
        """Atalho: mensagem curta na tela."""
        self.emitir({"tipo": "aviso", "texto": texto})

    def assinar(self):
        q = queue.Queue()
        with self.lock:
            self.ouvintes.append(q)
        q.put(self.ultimo_estado)
        return q

    def sair(self, q):
        with self.lock:
            if q in self.ouvintes:
                self.ouvintes.remove(q)


EVENTOS = Eventos()
