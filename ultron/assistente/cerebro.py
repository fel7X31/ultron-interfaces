"""Quem responde: o Claude (com ferramentas, o padrão) ou outra IA (ChatGPT, Gemini, Grok), escolhido na tela ou
por voz. Com outra IA não tem ferramenta: ela só conversa, e os comandos de voz rápidos continuam valendo.
"""
import threading
from collections import deque

from ..nucleo.config import CFG, persona, salvar_preferencias
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log_erro
from ..recursos import contas_ia, ias
from .sessao import SESSAO, lembrete

CONVERSA = deque(maxlen=12)  # as últimas falas com a outra IA, pra ela lembrar do assunto


def nome_atual():
    """'Claude Sonnet', 'Gemini'..."""
    return ias.nome(CFG["ia"], CFG["modelo"])


def usando_claude():
    return CFG["ia"] == "claude"


def escolher(ia, modelo=""):
    """Troca quem responde e guarda a escolha. ValueError se a IA não existe ou não está conectada."""
    if ia == "claude":
        _trocar_modelo_do_claude(modelo or CFG["modelo"])
    elif ia not in ias.PROVEDORES:
        raise ValueError(f"Não conheço a IA '{ia}'.")
    elif not ias.pronta(ia):
        raise ValueError(f"O {ias.nome(ia)} não está conectado. Entre com a sua conta na lista de IAs da tela "
                         f"ou coloque a {ias.PROVEDORES[ia]['chave']} no .env.")
    if ia != CFG["ia"]:
        CONVERSA.clear()
    CFG["ia"] = ia
    salvar_preferencias()
    EVENTOS.emitir({"tipo": "ia", "nome": nome_atual()})  # a tela e a barra mostram quem responde
    return nome_atual()


def _trocar_modelo_do_claude(modelo):
    if modelo not in ias.MODELOS_CLAUDE:
        raise ValueError(f"Não conheço o modelo '{modelo}' do Claude.")
    if modelo == CFG["modelo"]:
        return
    CFG["modelo"] = modelo
    SESSAO.parar()  # o modelo vai na hora de abrir o Claude: abre de novo já com o novo
    threading.Thread(target=SESSAO.iniciar, daemon=True).start()


def perguntar_a_outra_ia(texto):
    """A resposta da IA escolhida, no mesmo formato da sessão do Claude ({"result": ...} ou com "is_error")."""
    mensagens = [{"role": "system", "content": _instrucoes()}, *CONVERSA,
                 {"role": "user", "content": texto + lembrete()}]
    try:
        resposta = ias.perguntar(CFG["ia"], mensagens)
    except contas_ia.SemCota as erro:
        log_erro("outra_ia_sem_cota", erro, ia=CFG["ia"])
        return {"is_error": True, "result": f"O {nome_atual()} não respondeu: {erro}. Diga \"volta pro Claude\"."}
    except Exception as erro:
        log_erro("outra_ia_falhou", erro, ia=CFG["ia"])
        return {"is_error": True, "result": f"O {nome_atual()} não respondeu. Uma falha deles, não minha."}
    CONVERSA.extend([{"role": "user", "content": texto}, {"role": "assistant", "content": resposta}])
    return {"result": resposta}


def _instrucoes():
    nome = nome_atual()
    return persona() + (
        f"\n\n## Agora\nNesta conversa você roda no {nome}, sem ferramentas: não abre arquivo, não usa terminal "
        "nem internet. Ignore as instruções de ferramentas e atalhos acima. Se o pedido precisar disso, diga em uma "
        "frase que isso pede o Claude e que é só dizer \"volta pro Claude\". Se perguntarem qual inteligência roda "
        f"por baixo agora, é o {nome}.")
