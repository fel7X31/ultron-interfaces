"""A sessão do Claude Code que fica aberta e recebe uma fala por vez (stream-json pela entrada e saída padrão).

- SessaoClaude.perguntar(texto): manda a fala e espera a resposta (com o aviso rápido "Um instante..." no meio)
- SessaoClaude.interromper(): para o Claude na hora (barra de espaço) e a conversa continua
- rotulo_ferramenta(): o nome amigável do que ele está usando, pra tela mostrar
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid

from ..nucleo.claude_cli import claude_bin
from ..nucleo.config import CFG, ESTADO, RAIZ, persona
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log
from ..recursos.provas import lembrete_prova

ESPERA_AVISO = 0.3  # só fala "um instante" se o trabalho com ferramenta passar disso


# ---------------------------------------------------------------- o que vai junto de cada fala
def lembrete():
    """Vai junto de cada pedido: o modelo tende a se alongar quando acha muita coisa."""
    if CFG["modo_prova"]:
        return lembrete_prova()
    if CFG["modo_texto"]:
        return ("\n\n[modo texto: ele está digitando com você e vai LER a resposta, não ouvir. Responda direto, "
                "no seu tom, em até 6 frases. Pode usar listas curtas se ajudar. Sem aviso antes de ferramenta. "
                f"Trate-o por {CFG['nome']}, nunca por Senhor.]")
    return ("\n\n[modo voz: pergunta simples (conversa, confirmação, algo que você já sabe) = responda direto, "
            "sem aviso e sem ferramenta. Só se precisar de ferramenta, comece com uma frase curta de aviso (até 10 palavras). "
            f"Resposta final em no máximo 2 frases curtas, até 30 palavras. Trate-o por {CFG['nome']}, nunca por Senhor.]")


# ---------------------------------------------------------------- rótulos do que ele está usando
NOMES_SERVIDOR = {
    "geracorte": "GeraCorte",
    "geragrupos": "GeraGrupos",
    "panda-video": "Panda Video",
    "claude_ai_Google_Calendar": "Agenda",
    "claude_ai_Gmail": "Gmail",
    "claude_ai_Google_Drive": "Drive",
}
INTERNAS = {"ToolSearch", "TodoWrite", "BashOutput", "KillShell", "ListMcpResourcesTool", "ReadMcpResourceTool"}


def rotulo_ferramenta(nome, entrada):
    """None = não mostra (ferramenta interna)."""
    entrada = entrada or {}
    if nome in INTERNAS:
        return None
    if nome.startswith("mcp__"):
        servidor = nome.split("__")[1]
        for chave, rot in NOMES_SERVIDOR.items():
            if chave.lower() in servidor.lower():
                return rot
        return servidor.replace("claude_ai_", "").replace("_", " ")
    if nome == "Bash":
        cmd = entrada.get("command", "")
        if re.search(r"zernio\.py|redes_resumo|isca_resumo", cmd):
            return "Redes sociais"
        if "supabase" in cmd or "psql" in cmd:
            return "Banco de dados"
        if "Memória" in cmd or "/memory" in cmd:
            return "Memória"
        if "TaskNotes" in cmd:
            return "Kanban"
        if re.match(r"\s*(grep|rg|find|cat|head|tail|ls)\b", cmd):
            return "Lendo o vault"
        return "Terminal"
    caminho = str(entrada.get("file_path") or entrada.get("path") or entrada.get("pattern") or "")
    if nome in ("Write", "Edit", "MultiEdit"):
        return "Kanban" if "TaskNotes" in caminho else "Escrevendo nota"
    if nome in ("Read", "Grep", "Glob", "LS"):
        if "Memória" in caminho or "memory" in caminho:
            return "Memória"
        return "Kanban" if "TaskNotes" in caminho else "Lendo o vault"
    if nome == "Skill":
        return "Skill " + str(entrada.get("skill", ""))
    if nome in ("WebSearch", "WebFetch"):
        return "Internet"
    if nome in ("Task", "Agent"):
        return "Agente"
    return nome


# ---------------------------------------------------------------- uma pergunta em andamento
def _depois(segundos, funcao, *args):
    relogio = threading.Timer(segundos, funcao, args=args)
    relogio.daemon = True
    relogio.start()


class TurnoClaude:
    """Recebe o aviso rápido e a resposta final de uma pergunta."""

    def __init__(self, ao_avisar=None):
        self.fila = queue.Queue()
        self.entregue = False
        self.avisou = False
        self.ao_avisar = ao_avisar
        self.agendado = False
        self.trava = threading.Lock()
        self.marcas = {"envio": time.time()}  # tempos de cada etapa, pro log

    def marcar(self, nome):
        self.marcas.setdefault(nome, round(time.time() - self.marcas["envio"], 2))

    def entregar(self, resultado):
        if not self.entregue:
            self.entregue = True
            self.fila.put(resultado)

    def avisar(self, frase=None):
        """Fala o aviso rápido uma vez só por pergunta (o primeiro gatilho que chegar)."""
        with self.trava:
            if self.avisou or self.entregue or not self.ao_avisar:
                return
            self.avisou = True
        self.ao_avisar(frase)

    def pedir_aviso(self, frase=None):
        """Ele começou a usar ferramenta: se a resposta não sair em ESPERA_AVISO s, avisa."""
        with self.trava:
            if self.avisou or self.agendado:
                return
            self.agendado = True
        _depois(ESPERA_AVISO, self.avisar, frase)


# ---------------------------------------------------------------- o processo do Claude
class SessaoClaude:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.turno = None
        self.livre = threading.Event()  # o Claude fecha a rodada uns segundos depois da resposta
        self.livre.set()
        self.ferramentas_turno = []

    def comando(self):
        trava = f'"{sys.executable}" "{RAIZ / "hooks" / "trava.py"}"'
        ajustes = {"hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": trava}]}],
        }}
        cmd = [
            claude_bin(), "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",  # avisa o fim do texto antes de fechar a rodada
            "--permission-mode", "bypassPermissions",
            "--settings", json.dumps(ajustes),
            "--append-system-prompt", persona() + self.nota_pasta(),
        ]
        if CFG["contexto"] == "leve":
            cmd += ["--add-dir", str(CFG["pasta"])]
        if CFG["modelo"]:
            cmd += ["--model", CFG["modelo"]]
        if CFG["esforco"]:
            cmd += ["--effort", CFG["esforco"]]
        if CFG["bloquear"]:
            cmd += ["--disallowedTools", CFG["bloquear"]]
        return cmd

    def nota_pasta(self):
        return (f"\n\n## Pasta de trabalho\nA pasta de trabalho dele é `{CFG['pasta']}`. Caminhos relativos citados "
                "acima ficam dentro dela. Antes de criar ou mudar algo lá, leia o CLAUDE.md dela (só a parte que interessa).")

    def pasta_de_abertura(self):
        if CFG["contexto"] == "leve":
            leve = RAIZ / "cerebro"  # pasta vazia: o Claude não carrega o CLAUDE.md nem a memória da sua pasta
            leve.mkdir(exist_ok=True)
            return str(leve)
        return str(CFG["pasta"])

    def iniciar(self):
        ESTADO.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["ULTRON_ESTADO"] = str(ESTADO)
        env["ULTRON_PASTA"] = str(CFG["pasta"])
        self.livre.set()
        self.proc = subprocess.Popen(
            self.comando(), cwd=self.pasta_de_abertura(), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, encoding="utf-8",
        )
        threading.Thread(target=self._ler_saida, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._ler_erros, args=(self.proc,), daemon=True).start()

    def parar(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def vivo(self):
        return self.proc is not None and self.proc.poll() is None

    def _escrever(self, mensagem):
        self.proc.stdin.write(json.dumps(mensagem, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def interromper(self):
        """Barra de espaço no meio do trabalho: o Claude para na hora e a conversa continua."""
        turno = self.turno
        if not self.vivo() or not turno or turno.entregue:
            return False
        try:
            self._escrever({"type": "control_request", "request_id": uuid.uuid4().hex[:8],
                            "request": {"subtype": "interrupt"}})
        except (BrokenPipeError, OSError):
            pass
        turno.entregar({"result": "", "interrompido": True})
        return True

    def perguntar(self, texto, limite=300, ao_avisar=None, aviso_apos=None):
        """Manda a fala e espera a resposta. aviso_apos: se demorar isso (s), fala o aviso rápido mesmo sem ferramenta."""
        with self.lock:
            if not self.vivo():
                self.iniciar()
            espera = time.time()
            self.livre.wait(timeout=20)  # espera o Claude fechar a rodada anterior
            turno = TurnoClaude(ao_avisar)
            turno.marcas["esperou_rodada_s"] = round(time.time() - espera, 2)
            self.turno = turno
            self.livre.clear()
            self.ferramentas_turno = []
            self._escrever({"type": "user", "message": {
                "role": "user", "content": [{"type": "text", "text": texto + lembrete()}]}})
            if aviso_apos:
                _depois(aviso_apos, turno.avisar)
            try:
                return turno.fila.get(timeout=limite)
            except queue.Empty:
                self.parar()
                return {"is_error": True, "result": f"Demorei demais e reiniciei a conversa, {CFG['nome']}. Repita."}

    # -------------------------------------------------- leitura da saída do Claude (uma thread por processo)
    def _ler_saida(self, proc):
        iniciou = False
        texto_msg = ""  # texto da mensagem que o Claude está escrevendo agora
        for linha in proc.stdout:
            try:
                e = json.loads(linha)
            except ValueError:
                continue
            tipo = e.get("type")
            turno = self.turno
            if tipo == "system" and e.get("subtype") == "init":
                # O Claude manda esse aviso a cada pergunta; só o primeiro de cada processo interessa.
                if not iniciou:
                    iniciou = True
                    servidores = [(m.get("name"), m.get("status")) for m in e.get("mcp_servers", [])]
                    log({"evento": "init", "modelo": e.get("model"), "mcp": servidores,
                         "ferramentas": len(e.get("tools", []))})
            elif tipo == "stream_event":
                ev = e.get("event") or {}
                if ev.get("type") == "message_start":
                    texto_msg = ""
                    if turno:
                        turno.marcar("1a_mensagem_s")
                elif ev.get("type") == "message_delta" and (ev.get("delta") or {}).get("stop_reason") == "end_turn":
                    # Resposta final pronta: entrega já, sem esperar o Claude fechar a rodada.
                    if turno and texto_msg.strip():
                        turno.entregar({"result": texto_msg, "cedo": True})
            elif tipo == "assistant":
                for bloco in e.get("message", {}).get("content", []) or []:
                    if bloco.get("type") == "text":
                        texto_msg = (texto_msg + " " + bloco.get("text", "")).strip()
                    elif bloco.get("type") == "tool_use":
                        self._usou_ferramenta(turno, bloco, texto_msg)
                        texto_msg = ""
            elif tipo == "result":
                if turno:
                    turno.entregar(e)
                self.livre.set()
        if self.turno:
            self.turno.entregar({"type": "result", "is_error": True, "result": "A sessão do Claude fechou."})
        self.livre.set()

    def _usou_ferramenta(self, turno, bloco, texto_antes):
        if turno:
            turno.marcar("ferramenta_s")
            # Texto escrito antes da primeira ferramenta = aviso rápido ("Um instante, Senhor.").
            # Se ele foi direto pra ferramenta, toca uma frase pronta.
            turno.pedir_aviso(texto_antes or None)
        rot = rotulo_ferramenta(bloco.get("name", ""), bloco.get("input"))
        resumo = json.dumps(bloco.get("input") or {}, ensure_ascii=False)[:160]
        self.ferramentas_turno.append(f"{bloco.get('name')} {resumo}")
        if rot:
            EVENTOS.emitir({"tipo": "ferramenta", "rotulo": rot})

    def _ler_erros(self, proc):
        ESTADO.mkdir(exist_ok=True)
        with open(ESTADO / "claude-erros.log", "a", encoding="utf-8") as f:
            for linha in proc.stderr:
                f.write(linha)
                f.flush()


SESSAO = SessaoClaude()
