"""Comandos de voz que respondem na hora, sem passar pelo Claude (música, currículo, modo prova...).

Como funciona: o turno chama tentar(fala) antes de mandar a pergunta pro Claude. Cada comando é uma função
registrada com @comando, na ordem em que aparece aqui. Ela recebe a Fala e devolve:
    - um texto  -> é a resposta (dita em voz alta e mostrada na tela)
    - SILENCIO  -> tratou, mas não responde nada
    - None      -> não é com ela; tenta a próxima

Pra criar um comando novo: escreva uma função aqui com @comando, checando o tamanho da frase (frases longas
quase sempre são pedidos pro Claude) e uma regex pelas palavras-chave, já sem acento (veja normalizar()).
"""
import re
from dataclasses import dataclass, field

from ..nucleo.config import CFG, salvar_preferencias
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log_erro
from ..nucleo.texto import normalizar

SILENCIO = ""
COMANDOS = []


@dataclass
class Fala:
    """O que foi dito, já em formatos úteis pros comandos."""
    texto: str                      # como veio da transcrição
    aguardando_confirmacao: bool    # o Ultron acabou de perguntar "Confirma?"
    registro: dict                  # o que vai pro log deste turno (o comando pode anotar)
    palavras: list = field(init=False)
    frase: str = field(init=False)  # minúscula, sem acento e sem pontuação

    def __post_init__(self):
        self.palavras = normalizar(self.texto)
        self.frase = " ".join(self.palavras)

    def curta(self, ate):
        return len(self.palavras) <= ate


def comando(funcao):
    COMANDOS.append(funcao)
    return funcao


def tentar(fala):
    """A resposta do primeiro comando que reconhecer a fala, ou None (vai pro Claude)."""
    for funcao in COMANDOS:
        resposta = funcao(fala)
        if resposta is not None:
            return resposta
    return None


# ---------------------------------------------------------------- modo prova
LIGAR_PROVA = re.compile(r"\b(ativ\w*|lig\w*|entr\w*|comec\w*|inici\w*)\s+(o\s+|no\s+|em\s+)?modo\s+prova\b")
DESLIGAR_PROVA = re.compile(r"\b(desativ\w*|deslig\w*|sai\w*|encerr\w*|termin\w*|fech\w*)\s+(do\s+|o\s+|da\s+)?modo\s+prova\b")
SO_CONCORDANDO = {"ok", "okay", "boa", "beleza", "blz", "certo", "show", "valeu", "top", "isso", "otimo", "perfeito"}


def _modo_prova(ligado, fala):
    CFG["modo_prova"] = ligado
    salvar_preferencias()
    fala.registro["modo_prova"] = ligado


@comando
def ligar_prova(fala):
    if fala.curta(8) and LIGAR_PROVA.search(fala.frase):
        _modo_prova(True, fala)
        return f"Modo prova ativado, {CFG['nome']}. Cada questão será revisada duas vezes."


# Quadro de tarefas (modal com os cards e os prompts). Precisa de "quadro/painel/cards" ou "minhas tarefas",
# pra "abre o tarefas.md" ou "adiciona uma tarefa" continuarem indo pro Claude.
ABRIR_QUADRO = re.compile(r"\b(abr\w*|mostr\w*|ve|ver)\b.*\b(quadro|painel|cards?|minhas)\b.*\btarefas?\b"
                          r"|\b(abr\w*|mostr\w*)\b.*\btarefas?\b.*\b(quadro|painel|cards?)\b")
FECHAR_QUADRO = re.compile(r"\b(fech\w*|esconde\w*)\b.*\btarefas\b")


@comando
def quadro_tarefas(fala):
    if not fala.curta(9):
        return None
    if FECHAR_QUADRO.search(fala.frase):
        EVENTOS.emitir({"tipo": "tarefas", "abrir": False})
        return "Quadro de tarefas fechado."
    if ABRIR_QUADRO.search(fala.frase):
        EVENTOS.emitir({"tipo": "tarefas", "abrir": True})
        return "Quadro aberto. Cada card tem um prompt pronto, é só copiar."


# ---------------------------------------------------------------- currículo
# "Ultron, abre o currículo" / "quero analisar meu currículo" / "fecha o currículo": abre a tela na hora.
ABRIR_CURRICULO = re.compile(r"\b(abr\w*|mostr\w*|quero|vamos|bora|ir|vai|analis\w*|adapt\w*|atualiz\w*|mexer|editar)\b.*\bcurricul\w*")
FECHAR_CURRICULO = re.compile(r"\b(fech\w*|sai\w*|esconde\w*|tira\w*)\b.*\bcurricul\w*")
FALAS_CURRICULO = {"analisar": "Abrindo a análise do currículo. Vamos ver o que se salva.",
                   "adaptar": "Abrindo a adaptação. A folha em branco é minha especialidade.",
                   "": "Currículo aberto. Analisar ou adaptar, a escolha é sua."}


@comando
def fechar_curriculo(fala):
    if fala.curta(10) and FECHAR_CURRICULO.search(fala.frase):
        EVENTOS.emitir({"tipo": "curriculo", "abrir": False})
        return "Currículo fechado. O progresso ficou salvo."


@comando
def abrir_curriculo(fala):
    if fala.curta(10) and ABRIR_CURRICULO.search(fala.frase):
        modo = "analisar" if re.search(r"\banalis", fala.frase) else "adaptar" if re.search(r"\badapt", fala.frase) else ""
        EVENTOS.emitir({"tipo": "curriculo", "abrir": True, "modo": modo})
        return FALAS_CURRICULO[modo]


# ---------------------------------------------------------------- modo prova (fim)
@comando
def desligar_prova(fala):
    if fala.curta(8) and DESLIGAR_PROVA.search(fala.frase):
        _modo_prova(False, fala)
        return f"Modo prova encerrado, {CFG['nome']}."


@comando
def concordar_no_modo_prova(fala):
    """"ok", "boa": no modo prova ele não responde nada."""
    if CFG["modo_prova"] and not fala.aguardando_confirmacao and fala.palavras and fala.curta(2) \
            and all(p in SO_CONCORDANDO for p in fala.palavras):
        fala.registro["silencio"] = True
        return SILENCIO
