"""Modo prova: cada questão respondida fica salva; você marca certa/errada e escreve a correção.

As correções viram <sua pasta>/provas/correcoes.md (o Ultron lê antes de cada questão) e historico.md.
"""
import time
import uuid

from ..nucleo.arquivos import ler_json, salvar_json
from ..nucleo.config import CFG, ESTADO
from ..nucleo.eventos import EVENTOS

ARQUIVO = ESTADO / "provas.json"


def carregar_provas():
    return ler_json(ARQUIVO, []) or []


def salvar_provas(lista):
    salvar_json(ARQUIVO, lista, indent=1)
    _escrever_markdown(lista)
    EVENTOS.emitir({"tipo": "provas"})


def _escrever_markdown(lista):
    pasta = CFG["pasta"] / "provas"
    pasta.mkdir(parents=True, exist_ok=True)
    corrigidas = [q for q in lista if q.get("status") == "errada" and (q.get("correcao") or "").strip()]
    partes = ["# Correções do modo prova\n", "Questões em que o Ultron errou e o que estava certo. Ele lê isto antes de cada questão.\n"]
    for q in corrigidas:
        partes.append(f"## {q['quando'][:10]}\n**Questão:** {q['questao']}\n\n**Ultron respondeu (errado):** {q['resposta']}\n\n"
                      f"**Correção:** {q['correcao'].strip()}\n")
    (pasta / "correcoes.md").write_text("\n".join(partes), encoding="utf-8")
    certas = sum(1 for q in lista if q.get("status") == "certa")
    erradas = sum(1 for q in lista if q.get("status") == "errada")
    linhas = [f"# Histórico de provas\n\n{certas} certas · {erradas} erradas · {len(lista) - certas - erradas} sem marcar\n"]
    for q in lista:
        marca = {"certa": "✅ certa", "errada": "❌ errada"}.get(q.get("status"), "— sem marcar")
        linhas.append(f"- {q['quando'][:16]} · {marca} · {q['questao'][:120]}")
    (pasta / "historico.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def registrar_prova(questao, resposta):
    lista = carregar_provas()
    lista.append({"id": uuid.uuid4().hex[:10], "quando": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "questao": questao, "resposta": resposta, "status": None, "correcao": ""})
    salvar_provas(lista)


def atualizar_prova(pedido):
    """Marca certa/errada, guarda a correção ou apaga (pedido vem da tela)."""
    lista = carregar_provas()
    for q in lista:
        if q["id"] == pedido.get("id"):
            if pedido.get("apagar"):
                lista.remove(q)
                break
            if "status" in pedido and pedido["status"] in ("certa", "errada", None):  # só muda se veio no pedido
                q["status"] = pedido["status"]
            if "correcao" in pedido:
                q["correcao"] = str(pedido["correcao"])[:3000]
            break
    salvar_provas(lista)


def lembrete_prova():
    """Instruções que vão junto de cada pergunta quando o modo prova está ligado."""
    try:
        correcoes = (CFG["pasta"] / "provas" / "correcoes.md").read_text(encoding="utf-8")[-4000:]
    except FileNotFoundError:
        correcoes = ""
    return ("\n\n[MODO PROVA. Antes de responder: (1) resolva a questão; (2) revise do zero uma segunda vez, conferindo "
            "cada alternativa; só responda se as duas revisões concordarem (se não concordarem, revise a terceira vez e diga "
            "que ficou em dúvida). Em asserção-razão (\"I ... PORQUE II ...\"): julgue a asserção I sozinha, depois a II "
            "sozinha, pelo conteúdo; só então decida se a II justifica a I, também pelo conteúdo, nunca por palpite ou pela "
            "forma da frase. Responda com a alternativa e uma justificativa curta, em até 4 frases."
            + ("\nCorreções que " + CFG["nome"] + " já fez (respeite sempre):\n" + correcoes if correcoes.strip() else "")
            + f" Trate-o por {CFG['nome']}.]")
