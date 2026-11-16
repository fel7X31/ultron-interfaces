"""Quem responde: o Claude (com ferramentas, o padrão) ou outra IA (ChatGPT, Gemini, Grok), escolhido na tela ou
por voz. Com outra IA não tem ferramenta: ela só conversa, e os comandos de voz rápidos continuam valendo.
Se quem responde chega no limite de uso do plano, o turno passa pra próxima que ainda tem (ias.quem_responde) e
volta sozinho pra que você escolheu quando o limite dela libera.
"""
import threading
from collections import deque

from ..nucleo.config import CFG, persona, salvar_preferencias
from ..nucleo.eventos import EVENTOS
from ..nucleo.log import log, log_erro
from ..recursos import ias, limites, memoria
from .sessao import SESSAO, lembrete

CONVERSA = deque(maxlen=12)  # as últimas falas com a outra IA, pra ela lembrar do assunto
MOSTRADO = {"nome": None}  # quem a tela e a barra estão mostrando


def nome_atual():
    """'Claude Sonnet', 'Gemini'... de quem responde agora (outra, se a que você escolheu chegou no limite)."""
    return ias.nome(*ias.quem_responde())


def usando_claude():
    return ias.quem_responde()[0] == "claude"


def escolher(ia, modelo=""):
    """Troca quem responde e guarda a escolha. ValueError se a IA não existe ou não está conectada.
    Escolhida na mão, ela tenta de novo mesmo se tinha chegado no limite."""
    modelo = (modelo or CFG["modelo"]) if ia == "claude" else ""
    if ia == "claude" and modelo not in ias.MODELOS_CLAUDE:
        raise ValueError(f"Não conheço o modelo '{modelo}' do Claude.")
    if ia != "claude" and ia not in ias.PROVEDORES:
        raise ValueError(f"Não conheço a IA '{ia}'.")
    if not ias.pronta(ia):
        raise ValueError(f"O {ias.nome(ia)} não está conectado. Entre com a sua conta na lista de IAs da tela "
                         f"ou coloque a {ias.PROVEDORES[ia]['chave']} no .env.")
    limites.liberar(ia, modelo)
    if ia == "claude":
        _trocar_modelo_do_claude(modelo)
    if ia != CFG["ia"]:
        CONVERSA.clear()
    CFG["ia"] = ia
    salvar_preferencias()
    mostrar_quem_responde()
    return nome_atual()


def mostrar_quem_responde():
    """Conta pra tela e pra barra quem responde agora."""
    MOSTRADO["nome"] = nome_atual()
    EVENTOS.emitir({"tipo": "ia", "nome": MOSTRADO["nome"]})


def conferir_quem_responde():
    """Roda nas rotinas: se quem responde mudou sozinho (o limite da que você escolheu liberou), atualiza a tela."""
    if nome_atual() != MOSTRADO["nome"]:
        mostrar_quem_responde()


def anotar_limite(ia, modelo, limite):
    """Ela chegou no limite do plano: anota até quando (as próximas perguntas vão pra outra) e devolve a frase."""
    chave = limites.chave(ia, limite.get("tipo", ""))
    ate = limites.esgotar(chave, limite.get("ate"))
    log({"evento": "limite", "ia": chave, "ate": round(ate)})
    quem = ias.nome(*chave.split(":"))  # "Claude" (vale pra todos os modelos), "Claude Opus", "ChatGPT"...
    return f"O {quem} chegou no limite de uso, libera {limites.quando(ate)}."


def _trocar_modelo_do_claude(modelo):
    if modelo == CFG["modelo"]:
        return
    CFG["modelo"] = modelo
    SESSAO.parar()  # o modelo vai na hora de abrir o Claude: abre de novo já com o novo
    threading.Thread(target=SESSAO.iniciar, daemon=True).start()


def perguntar_a_outra_ia(texto, ia):
    """A resposta da IA (ChatGPT, Gemini...), no mesmo formato da sessão do Claude ({"result": ...} ou com
    "is_error"; com "limite" quando a conta dela chegou no limite do plano)."""
    mensagens = [{"role": "system", "content": _instrucoes(ia)}, *CONVERSA,
                 {"role": "user", "content": texto + lembrete()}]
    try:
        resposta = ias.perguntar(ia, mensagens)
    except limites.SemCota as erro:
        log_erro("outra_ia_sem_cota", erro, ia=ia)
        return {"is_error": True, "result": f"O {ias.nome(ia)} chegou no limite de uso.", "limite": {"ate": erro.ate}}
    except Exception as erro:
        log_erro("outra_ia_falhou", erro, ia=ia)
        return {"is_error": True, "result": f"O {ias.nome(ia)} não respondeu. Uma falha deles, não minha."}
    CONVERSA.extend([{"role": "user", "content": texto}, {"role": "assistant", "content": resposta}])
    return {"result": resposta}


def _instrucoes(ia):
    nome = ias.nome(ia)
    volta = limites.libera_em("claude")
    pedir_o_claude = (f", que chegou no limite de uso e volta {limites.quando(volta)}" if volta
                      else " e que é só dizer \"volta pro Claude\"")
    return persona() + memoria.para_o_prompt() + (
        f"\n\n## Agora\nNesta conversa você roda no {nome}, sem ferramentas: não abre arquivo, não usa terminal "
        "nem internet. Ignore as instruções de ferramentas e atalhos acima. Se o pedido precisar disso, diga em uma "
        f"frase que isso pede o Claude{pedir_o_claude}. Se perguntarem qual inteligência roda "
        f"por baixo agora, é o {nome}.")
