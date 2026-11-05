"""Quando a trava abre: o Ultron perguntou "Confirma?" e você disse que sim, ou você já deu a permissão no pedido.

Enquanto a trava está aberta existe o arquivo .estado/confirmado (o hooks/trava.py olha pra ele).
"""
import re

from ..nucleo.texto import normalizar

AFIRMACOES = {"sim", "pode", "manda", "isso", "ok", "okay", "fechado", "vai", "faz", "faca", "beleza", "claro",
              "positivo", "certo", "bora", "autorizo", "autorizado", "liberado", "libero", "permito", "permitido",
              "confia", "segue", "prossiga", "executa", "aham", "uhum", "s", "yes", "yep"}
# Começo de palavra que já vale: "confirm", "confirme", "confirmo", "confirmado" (o Whisper às vezes corta)...
RAIZES_SIM = ("confirm", "autoriz", "liber", "permit")
# Antes de a palavra de sim aparecer, pode ter "ultron", "é", "eu"...: "Ultron, pode", "eu confirmo", "é, pode sim"
ENCHIMENTO = {"ultron", "e", "eu", "ja", "falei", "disse", "que", "ta", "entao", "ah", "ai", "tudo", "bem", "pois", "sim",
              "senhor", "cara", "mano", "pode", "voce", "te", "agora"}
NEGACOES = {"nao", "cancela", "cancelar", "espera", "pare", "nunca", "jamais"}

# Permissão dada já no pedido: "cria o arquivo, pode fazer sem perguntar", "você tem permissão pra mexer nisso".
AUTORIZOU_NO_PEDIDO = re.compile(
    r"\b(sem (me )?(perguntar|pedir|confirmar|confirmacao)|nao precisa (me )?(perguntar|pedir|confirmar)|"
    r"(ja )?(te )?(dou|tem|tens|voce tem) (a )?(minha )?(permissao|autorizacao)|(eu )?(te )?(autorizo|permito)|"
    r"ta (liberado|autorizado|permitido)|pode (fazer|criar|salvar|escrever|editar|mexer|mudar|apagar|mandar|enviar|"
    r"rodar|executar|instalar|mover|marcar|agendar|anotar|adicionar|colocar|tirar|trocar|alterar|atualizar)( sim)?( sem medo)?\b)")
PROIBIU = re.compile(r"\b(nao|nunca) (pode|faca|faz|mexa|apague|mande)\b")


def _eh_sim(p):
    return p in AFIRMACOES or p.startswith(RAIZES_SIM)


def eh_confirmacao(texto):
    """Resposta ao "Confirma?": sim, pode, confirme, "Ultron, pode fazer", "eu confirmo, pode criar o arquivo"..."""
    palavras = normalizar(texto)
    if not palavras or len(palavras) > 15 or any(p in NEGACOES for p in palavras):
        return False
    for p in palavras[:4]:  # a palavra de sim vem logo no começo
        if _eh_sim(p):
            return True
        if p not in ENCHIMENTO:
            return False
    return False


def autorizou_no_pedido(texto):
    frase = " ".join(normalizar(texto))
    return bool(AUTORIZOU_NO_PEDIDO.search(frase)) and not PROIBIU.search(frase)


def pediu_confirmacao(resposta):
    """A resposta do Ultron termina perguntando "Confirma?"."""
    return "confirma" in " ".join(normalizar(resposta[-80:]))
