"""Comandos de voz do controle do PC: volume, Spotify, janelas, programas, Configurações, brilho e uso.

Respondem na hora, sem o Claude. O que não estiver aqui (ou for mais complicado) segue pro Claude, que controla o
PC pelo atalhos/pc.py.
"""
import re

from ..nucleo.log import log_erro
from ..recursos import pc
from ..recursos.pc import midia, programas, sistema
from .comandos import comando

NUMEROS = {"zero": 0, "dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
           "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100, "metade": 50, "maximo": 100, "minimo": 0}
SUBIR = re.compile(r"\b(aument\w*|sob\w*|sub\w*|mais alto)\b")
DESCER = re.compile(r"\b(abaix\w*|diminu\w*|baix\w*|reduz\w*|mais baixo)\b")
ATE = re.compile(r"\b(pra|para|ate|no|na)\s+(\d+|" + "|".join(NUMEROS) + r")\b")  # "aumenta pra 80" = fica em 80
VOLUME = re.compile(r"\b(volume|som)\b")
MUDO = re.compile(r"\b(muta\w*|mute|silenci\w*|tira (o )?som|sem som|(coloca|poe|bota) no mudo)\b")
DESMUDO = re.compile(r"\b(desmut\w*|unmute|tira (do|o) mudo|som de volta|ativa (o )?som)\b")
SPOTIFY = re.compile(r"\bspotify\b")
PAUSAR = re.compile(r"\b(pausa\w*|pause|para|parar)\b")
TOCAR = re.compile(r"\b(toca\w*|tocar|play|continua\w*|solta\w*|despausa\w*)\b")
PROXIMA = re.compile(r"\b(proxim\w*|pula\w*|pular|passa\w*|avanca\w*)\b")
ANTERIOR = re.compile(r"\b(anterior|volta\w*|voltar)\b")
BLOQUEAR = re.compile(r"\bbloque\w* (o |a )?(pc|computador|tela|notebook)\b")
AREA = re.compile(r"\b(minimiz\w* tudo|area de trabalho)\b")
ABRIR = re.compile(r"^(?:ultron )?(?:abr\w*|inicia\w*|executa\w*)\s+(?:o |a |os |as )?(.+)$")
FECHAR = re.compile(r"^(?:ultron )?(?:fech\w*|encerr\w*)\s+(?:o |a |os |as )?(.+)$")
CONFIGURACOES = re.compile(r"\b(abr\w*|mostr\w*)\b.*\bconfiguraco\w* (?:d[eoa]s? )?(.+)$")
BRILHO = re.compile(r"\bbrilho\b")
USO = re.compile(r"\b(uso|como (esta|ta)) (do |o |a )?(pc|computador|notebook|processador|memoria)\b"
                 r"|\b(temperatura|memoria|processador) do (pc|computador|notebook)\b")
TOCANDO = re.compile(r"\b(que|qual) (musica )?(esta|ta) tocando\b|\bque musica e essa\b")


def _executar(acao, alvo, fala):
    """Roda a ação do PC e devolve a frase (ou o erro, dito numa frase)."""
    fala.registro["pc"] = f"{acao} {alvo}".strip()
    try:
        return pc.executar(acao, alvo)
    except ValueError as erro:
        return str(erro)
    except Exception as erro:
        log_erro("pc_falhou", erro, acao=acao)
        return "O Windows não obedeceu dessa vez."


def _numero(fala):
    """O primeiro número falado (30, "trinta", "metade"...), ou None."""
    for palavra in fala.palavras:
        if palavra.isdigit():
            return int(palavra)
        if palavra in NUMEROS:
            return NUMEROS[palavra]
    return None


def _subir_ou_descer(fala, nome, padrao):
    """("mais_volume", "10"), ("volume", "80") etc. pra "aumenta o volume", "abaixa pra 80"..., ou None."""
    numero = _numero(fala)
    if numero is not None and (ATE.search(fala.frase) or not (SUBIR.search(fala.frase) or DESCER.search(fala.frase))):
        return nome, str(numero)
    if SUBIR.search(fala.frase):
        return "mais_" + nome, str(numero or padrao)
    if DESCER.search(fala.frase):
        return "menos_" + nome, str(numero or padrao)
    return None


@comando
def mudo(fala):
    if not fala.curta(8):
        return None
    if DESMUDO.search(fala.frase):
        return _executar("som", "", fala)
    if MUDO.search(fala.frase):
        return _executar("mudo", "", fala)


@comando
def volume(fala):
    if not fala.curta(9) or not VOLUME.search(fala.frase) or SPOTIFY.search(fala.frase):
        return None
    pedido = _subir_ou_descer(fala, "volume", 10)
    return _executar(*pedido, fala) if pedido else None


@comando
def spotify(fala):
    """Tocar, pausar, pular e voltar no que estiver tocando no PC (o Spotify ou outro)."""
    if not fala.curta(8) or not SPOTIFY.search(fala.frase) or ABRIR.match(fala.frase) or FECHAR.match(fala.frase):
        return None
    if PROXIMA.search(fala.frase):
        return _executar("proxima", "", fala)
    if ANTERIOR.search(fala.frase):
        return _executar("anterior", "", fala)
    quer_tocar = TOCAR.search(fala.frase) and not PAUSAR.search(fala.frase)
    if not quer_tocar and not PAUSAR.search(fala.frase):
        return None
    if bool(midia.tocando().get("tocando")) == bool(quer_tocar):
        return "Já está tocando." if quer_tocar else "Já está pausado."
    return _executar("tocar_pausar", "", fala)


@comando
def janelas_e_bloqueio(fala):
    if not fala.curta(8):
        return None
    if BLOQUEAR.search(fala.frase):
        return _executar("bloquear", "", fala)
    if AREA.search(fala.frase):
        return _executar("area_de_trabalho", "", fala)


@comando
def configuracoes_do_windows(fala):
    achou = CONFIGURACOES.search(fala.frase) if fala.curta(8) else None
    if achou and achou.group(2) in sistema.PAGINAS:
        return _executar("configuracoes", achou.group(2), fala)


@comando
def abrir_ou_fechar_programa(fala):
    """Só os programas conhecidos (spotify, chrome, calculadora...): o resto vai pro Claude."""
    if not fala.curta(6):
        return None
    for regex, acao in ((ABRIR, "abrir"), (FECHAR, "fechar")):
        achou = regex.match(fala.frase)
        if achou and programas.conhecido(achou.group(1)):
            return _executar(acao, achou.group(1), fala)


@comando
def brilho(fala):
    if not fala.curta(9) or not BRILHO.search(fala.frase):
        return None
    pedido = _subir_ou_descer(fala, "brilho", 20)
    return _executar(*pedido, fala) if pedido else None


@comando
def uso_e_musica_do_pc(fala):
    if not fala.curta(9):
        return None
    if USO.search(fala.frase):
        return _executar("uso", "", fala)
    if TOCANDO.search(fala.frase):
        return _executar("tocando", "", fala)
