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
from ..recursos import musica
from ..voz.transcricao import IDIOMA, liberar_idioma

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


# ---------------------------------------------------------------- modo entrevista
LIGAR_ENTREVISTA = re.compile(r"\bmod\w* (d[eo] )?entre ?v\w*|\binterview mode\b")  # a transcrição erra: "módulo entrevistas", "modo entre vídeos"
FIM_ENTREVISTA = re.compile(r"^(ultron )?(terminar|encerrar|end( the)? interview)\b"
                            r"|\b(sai\w*|deslig\w*|termin\w*|encerr\w*) (do |o |da )?modo (de )?entrevista\b")


def _modo_entrevista(ligado):
    if IDIOMA["livre"] == ligado:
        return
    liberar_idioma(ligado)
    EVENTOS.emitir({"tipo": "entrevista", "ligado": ligado})
    EVENTOS.aviso("Ouvindo em inglês." if ligado else "Ouvindo em português.")


@comando
def idioma_da_entrevista(fala):
    """Só troca o idioma da transcrição e avisa a tela. Quem conduz a entrevista é o Claude (persona), então devolve None."""
    if not fala.curta(8):
        return
    if FIM_ENTREVISTA.search(fala.frase):
        _modo_entrevista(False)
    elif LIGAR_ENTREVISTA.search(fala.frase):
        _modo_entrevista(True)


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


TOCAR_BUSCA = re.compile(r"^(?:ultron |ei ultron |ultron por favor )?(?:toca|toque|tocar|coloca|bota|poe|quero ouvir|"
                         r"quero escutar|bota pra tocar|coloca pra tocar) (.+)$")
GENERICAS = {"musica", "musicas", "uma", "um", "som", "a", "o", "ai", "de", "novo", "pra", "mim", "alguma", "qualquer", "lofi",
             "playlist", "radio", "ela", "essa", "isso", "ali", "aqui", "por", "favor", "la", "tocar", "player", "minha", "minhas"}
NAO_MUSICA = {"agenda", "tarefa", "tarefas", "lembrete", "lembra", "lista", "alarme", "email", "calendario", "nota", "notas",
              "compromisso", "evento", "arquivo", "pasta", "curriculo", "tela", "volume", "brilho", "timer", "despertador"}
MUSICA = re.compile(r"\b(musica\w*|som|playlist|lofi|radio|player|faixa)\b")
MUSICA_ACOES = [
    ("proxima", re.compile(r"\b(proxim\w*|pula\w*|pular|passa\w*|troca\w*|outra)\b"), "Próxima."),
    ("anterior", re.compile(r"\b(anterior|volta\w*|voltar)\b"), "Voltando uma."),
    ("parar", re.compile(r"\b(para|parar|desliga\w*|chega)\b"), "Música desligada."),
    ("pausar", re.compile(r"\b(pausa\w*|pause)\b"), "Pausei."),
    ("fechar", re.compile(r"\b(fech\w*|esconde\w*)\b"), "Minimizei o player. A música continua."),
    ("tocar", re.compile(r"\b(toca\w*|tocar|coloca\w*|bota\w*|liga\w*|play|continua\w*|solta\w*|ouv\w*)\b"), "Tocando."),
    ("abrir", re.compile(r"\b(abr\w*|mostr\w*)\b"), "Player aberto."),
]


@comando
def tocar_musica_pesquisada(fala):
    busca = TOCAR_BUSCA.match(fala.frase) if fala.curta(12) else None
    if not busca or not set(busca.group(1).split()) - GENERICAS or set(fala.palavras) & NAO_MUSICA:
        return None
    q = re.sub(r"^(?:a |o )?(?:musica |som )?", "", busca.group(1)).strip()
    try:
        achou = musica.buscar(q, limite=1)
    except Exception as erro:
        log_erro("musica_busca_falhou", erro)
        achou = []
    if not achou:
        return "Não achei essa música no YouTube."
    item = musica.avulsa(achou[0])
    EVENTOS.emitir({"tipo": "musica", "acao": "tocar_item", "item": item})
    fala.registro["musica"] = "busca:" + q
    nome = re.sub(r"\s*[\(\[].*?[\)\]]", "", item["titulo"]).strip() or item["titulo"]
    return f"Tocando {nome}."


@comando
def controlar_musica(fala):
    if not fala.curta(8) or not MUSICA.search(fala.frase):
        return None
    for acao, regex, resposta in MUSICA_ACOES:
        if regex.search(fala.frase):
            EVENTOS.emitir({"tipo": "musica", "acao": acao})
            fala.registro["musica"] = acao
            return resposta
    return None


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
