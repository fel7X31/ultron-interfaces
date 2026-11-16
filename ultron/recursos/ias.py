"""Outras IAs além do Claude (ChatGPT, Gemini, Grok): pela chave da API ou pela sua própria conta.

Com chave no .env (OPENAI_API_KEY, GEMINI_API_KEY, XAI_API_KEY), vai pela API. Todas aceitam o mesmo formato
(o "chat completions" da OpenAI), então uma função só serve pra todas. Sem chave, o Gemini e o ChatGPT ainda
funcionam pela sua conta (Google e ChatGPT), pelos programas deles (veja contas_ia.py). Sem nenhum dos dois, a IA
aparece desligada. O modelo muda no .env (ULTRON_MODELO_CHATGPT, ULTRON_MODELO_GEMINI, ULTRON_MODELO_GROK).
Outra IA com esse mesmo formato (DeepSeek, Mistral, Ollama...) entra com uma linha em PROVEDORES.

Quando quem responde chega no limite de uso do plano, quem_responde() passa pra próxima da fila que ainda tem
(o Claude primeiro, porque ele tem ferramentas) e volta pra que você escolheu quando o limite dela libera.
"""
import json
import urllib.error
import urllib.request

from ..nucleo.config import CFG, variavel
from . import contas_ia, limites

PROVEDORES = {
    "chatgpt": {"nome": "ChatGPT", "url": "https://api.openai.com/v1/chat/completions",
                "chave": "OPENAI_API_KEY", "modelo": "gpt-6.1-terra"},
    "gemini": {"nome": "Gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "chave": "GEMINI_API_KEY", "modelo": "gemini-3.8-flash"},
    "grok": {"nome": "Grok", "url": "https://api.x.ai/v1/chat/completions",
             "chave": "XAI_API_KEY", "modelo": "grok-4.7"},
}
MODELOS_CLAUDE = {"sonnet": "Claude Sonnet", "opus": "Claude Opus", "haiku": "Claude Haiku"}
ESFORCOS_CLAUDE = ("low", "medium", "high", "xhigh", "max")  # o --effort do Claude Code
ESFORCOS_OUTRAS = ("low", "medium", "high")                  # o reasoning_effort da API e do Codex
NOMES_DO_ESFORCO = {"low": "Baixo", "medium": "Médio", "high": "Alto", "xhigh": "Muito alto", "max": "Máximo"}


def modelo(ia):
    """O modelo que a IA usa: o do .env, ou o padrão."""
    return variavel(f"ULTRON_MODELO_{ia.upper()}", PROVEDORES[ia]["modelo"])


def chave(ia, modelo=""):
    """Como cada opção fica nas preferências: "claude:opus", "chatgpt"..."""
    return f"claude:{modelo}" if ia == "claude" else ia


def esforcos(ia):
    """Os esforços que dá pra escolher pra essa IA (vazio se ela não tem esse ajuste, como o Gemini pela conta)."""
    if ia == "claude":
        return ESFORCOS_CLAUDE
    return ESFORCOS_OUTRAS if ia == "chatgpt" or (ia == "gemini" and tem_chave(ia)) else ()


def esforco(ia, modelo=""):
    """O esforço que você escolheu pra essa IA ou modelo do Claude ("" = o padrão do modelo, sem limitar nada)."""
    return CFG["esforcos"].get(chave(ia, modelo), "")


def tem_chave(ia):
    return ia in PROVEDORES and bool(variavel(PROVEDORES[ia]["chave"]))


def pronta(ia):
    """Dá pra usar agora: o Claude sempre; as outras com chave ou depois que você entrou com a sua conta."""
    return ia == "claude" or tem_chave(ia) or contas_ia.conectado(ia)


def nome(ia, modelo_claude=""):
    """'Claude Opus', 'Gemini'..."""
    if ia == "claude":
        return MODELOS_CLAUDE.get(modelo_claude, "Claude")
    return PROVEDORES[ia]["nome"] if ia in PROVEDORES else ia


def fila():
    """A ordem de quem responde: a que você escolheu, o Claude (o seu modelo e depois os outros) e as outras IAs."""
    escolhida = (CFG["ia"], CFG["modelo"] if CFG["ia"] == "claude" else "")
    claude = [("claude", m) for m in (CFG["modelo"], *MODELOS_CLAUDE)]
    return list(dict.fromkeys([escolhida, *claude, *((ia, "") for ia in PROVEDORES)]))


def quem_responde():
    """(ia, modelo) de quem responde agora: a primeira da fila que está pronta e ainda tem limite.
    Se todas chegaram no limite, a que você escolheu."""
    for ia, modelo in fila():
        if pronta(ia) and not limites.libera_em(ia, modelo):
            return ia, modelo
    return fila()[0]


def opcoes():
    """O que a tela mostra pra escolher: os modelos do Claude e as outras IAs (desligadas se faltar a chave), com
    "sem limite, volta às 15:00" nas que chegaram no limite do plano."""
    claude = [{"ia": "claude", "modelo": m, "nome": n, "ligada": True} for m, n in MODELOS_CLAUDE.items()]
    outras = [{"ia": ia, "modelo": modelo(ia), "nome": p["nome"], "ligada": pronta(ia), "chave": p["chave"],
               "entrar": contas_ia.CONTAS[ia]["com"] if ia in contas_ia.CONTAS and not pronta(ia) else ""}
              for ia, p in PROVEDORES.items()]
    return [{**o, "limite": _nota_de_limite(o["ia"], o["modelo"]), "esforco": esforco(o["ia"], o["modelo"]),
             "esforcos": [{"valor": v, "nome": NOMES_DO_ESFORCO[v]} for v in esforcos(o["ia"])]}
            for o in claude + outras]


def _nota_de_limite(ia, modelo):
    ate = limites.libera_em(ia, modelo)
    return f"sem limite, volta {limites.quando(ate)}" if ate else ""


def perguntar(ia, mensagens, limite=60):
    """Manda a conversa ({"role", "content"}...) pra IA e devolve o texto da resposta.

    Com chave, vai pela API, com o esforço que você escolheu (se a API recusar o esforço, vai no padrão dela).
    Sem chave, vai pela sua conta, se você já entrou.
    """
    provedor = PROVEDORES[ia]
    chave = variavel(provedor["chave"])
    if not chave and contas_ia.conectado(ia):
        return contas_ia.perguntar(ia, mensagens, variavel(f"ULTRON_MODELO_{ia.upper()}"), esforco=esforco(ia))
    if not chave:
        raise ValueError(f"O {provedor['nome']} não está conectado: entre com a sua conta ou coloque a "
                         f"{provedor['chave']} no .env.")
    corpo = {"model": modelo(ia), "messages": mensagens}
    pensar = {"reasoning_effort": esforco(ia)} if esforco(ia) else {}
    try:
        return _enviar(provedor["url"], chave, {**corpo, **pensar}, limite)
    except urllib.error.HTTPError as erro:
        if erro.code != 400 or not pensar:
            raise
        return _enviar(provedor["url"], chave, corpo, limite)  # a API não aceitou o esforço: vai no padrão dela


def _enviar(url, chave, corpo, limite):
    pedido = urllib.request.Request(url, data=json.dumps(corpo).encode(), headers={
        "Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=limite) as r:
            resposta = json.load(r)
    except urllib.error.HTTPError as erro:
        if erro.code == 429:  # a chave chegou no limite (ou acabou o crédito)
            raise limites.SemCota() from erro
        raise
    return (resposta["choices"][0]["message"].get("content") or "").strip()
