"""Outras IAs além do Claude (ChatGPT, Gemini, Grok): pela chave da API ou pela sua própria conta.

Com chave no .env (OPENAI_API_KEY, GEMINI_API_KEY, XAI_API_KEY), vai pela API. Todas aceitam o mesmo formato
(o "chat completions" da OpenAI), então uma função só serve pra todas. Sem chave, o Gemini e o ChatGPT ainda
funcionam pela sua conta (Google e ChatGPT), pelos programas deles (veja contas_ia.py). Sem nenhum dos dois, a IA
aparece desligada. O modelo muda no .env (ULTRON_MODELO_CHATGPT, ULTRON_MODELO_GEMINI, ULTRON_MODELO_GROK).
Outra IA com esse mesmo formato (DeepSeek, Mistral, Ollama...) entra com uma linha em PROVEDORES.
"""
import json
import urllib.error
import urllib.request

from ..nucleo.config import variavel
from . import contas_ia

PROVEDORES = {
    "chatgpt": {"nome": "ChatGPT", "url": "https://api.openai.com/v1/chat/completions",
                "chave": "OPENAI_API_KEY", "modelo": "gpt-6.1-terra", "rapido": {"reasoning_effort": "low"}},
    "gemini": {"nome": "Gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "chave": "GEMINI_API_KEY", "modelo": "gemini-3.8-flash", "rapido": {"reasoning_effort": "low"}},
    "grok": {"nome": "Grok", "url": "https://api.x.ai/v1/chat/completions",
             "chave": "XAI_API_KEY", "modelo": "grok-4.7", "rapido": {}},
}
MODELOS_CLAUDE = {"sonnet": "Claude Sonnet", "opus": "Claude Opus", "haiku": "Claude Haiku"}


def modelo(ia):
    """O modelo que a IA usa: o do .env, ou o padrão."""
    return variavel(f"ULTRON_MODELO_{ia.upper()}", PROVEDORES[ia]["modelo"])


def tem_chave(ia):
    return ia in PROVEDORES and bool(variavel(PROVEDORES[ia]["chave"]))


def pronta(ia):
    """Dá pra usar agora: tem chave ou você já entrou com a sua conta."""
    return tem_chave(ia) or contas_ia.conectado(ia)


def nome(ia, modelo_claude=""):
    """'Claude Opus', 'Gemini'..."""
    if ia == "claude":
        return MODELOS_CLAUDE.get(modelo_claude, "Claude")
    return PROVEDORES[ia]["nome"] if ia in PROVEDORES else ia


def opcoes():
    """O que a tela mostra pra escolher: os modelos do Claude e as outras IAs (desligadas se faltar a chave)."""
    claude = [{"ia": "claude", "modelo": m, "nome": n, "ligada": True} for m, n in MODELOS_CLAUDE.items()]
    outras = [{"ia": ia, "modelo": modelo(ia), "nome": p["nome"], "ligada": pronta(ia), "chave": p["chave"],
               "entrar": contas_ia.CONTAS[ia]["com"] if ia in contas_ia.CONTAS and not pronta(ia) else ""}
              for ia, p in PROVEDORES.items()]
    return claude + outras


def perguntar(ia, mensagens, limite=60):
    """Manda a conversa ({"role", "content"}...) pra IA e devolve o texto da resposta.

    Com chave, vai pela API e pede a resposta rápida (pensando pouco); se a API recusar esse pedido, tenta de novo
    do jeito padrão. Sem chave, vai pela sua conta, se você já entrou.
    """
    provedor = PROVEDORES[ia]
    chave = variavel(provedor["chave"])
    if not chave and contas_ia.conectado(ia):
        return contas_ia.perguntar(ia, mensagens, variavel(f"ULTRON_MODELO_{ia.upper()}"))
    if not chave:
        raise ValueError(f"O {provedor['nome']} não está conectado: entre com a sua conta ou coloque a "
                         f"{provedor['chave']} no .env.")
    corpo = {"model": modelo(ia), "messages": mensagens}
    try:
        return _enviar(provedor["url"], chave, {**corpo, **provedor["rapido"]}, limite)
    except urllib.error.HTTPError as erro:
        if erro.code != 400 or not provedor["rapido"]:
            raise
        return _enviar(provedor["url"], chave, corpo, limite)


def _enviar(url, chave, corpo, limite):
    pedido = urllib.request.Request(url, data=json.dumps(corpo).encode(), headers={
        "Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=limite) as r:
        resposta = json.load(r)
    return (resposta["choices"][0]["message"].get("content") or "").strip()
