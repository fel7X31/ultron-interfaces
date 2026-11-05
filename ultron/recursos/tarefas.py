"""Tarefas: lê e escreve o tarefas.md da sua pasta, uma linha por tarefa, com campos no fim (Obsidian/Dataview):
    "- [ ] estudar backend [dif:: 4] [prio:: alta] [prazo:: 2026-11-20]"
dif: 1 muito fácil … 5 muito difícil · prio: alta, media ou baixa · prazo: AAAA-MM-DD (opcional).

O Ultron preenche sozinho o que falta (avaliar_tarefas) e escreve, pra cada pendente, um resumo, o tempo estimado
e um prompt pronto pra copiar e colar. Isso fica em .estado/tarefas-detalhes.json, pelo texto da tarefa.
No painel e no quadro de tarefas (modal da tela) dá pra trocar qualquer campo à mão.
"""
import json
import re
import threading
import time

from ..nucleo.arquivos import ler_json, salvar_json
from ..nucleo.claude_cli import claude_json
from ..nucleo.config import CFG, ESTADO
from ..nucleo.log import log, log_erro
from .paineis import PAINEIS, avisar_paineis

RE_TAREFA = re.compile(r"(\s*[-*]\s*\[)( |x|X)(\]\s*)(.+?)\s*$")
RE_CAMPO = re.compile(r"\s*\[(dif|prio|prazo)::\s*([^\]]*?)\s*\]\s*$")
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
PRIORIDADES = ("alta", "media", "baixa")
DETALHES = ESTADO / "tarefas-detalhes.json"
TRAVA = threading.Lock()
AVALIACAO = {"rodando": False, "proxima": time.time() + 30}  # deixa o Ultron aquecer primeiro
POR_VEZ = 5  # tarefas por consulta: cada uma ganha um prompt, então a resposta é grande


def arquivo():
    return CFG["pasta"] / "tarefas.md"


def _ler_linhas():
    return arquivo().read_text(encoding="utf-8").splitlines() if arquivo().exists() else ["# Tarefas", ""]


def _gravar_linhas(linhas):
    arquivo().write_text("\n".join(linhas) + "\n", encoding="utf-8")


def ler_detalhes():
    dados = ler_json(DETALHES, {})
    return dados if isinstance(dados, dict) else {}


def separar_campos(texto):
    """'estudar [dif:: 4] [prazo:: 2026-11-20]' -> ('estudar', {'dif': 4, 'prio': '', 'prazo': '2026-11-20'})."""
    campos = {"dif": 0, "prio": "", "prazo": ""}
    while True:
        m = RE_CAMPO.search(texto)
        if not m:
            return texto, campos
        chave, valor = m.group(1), m.group(2).strip().lower().replace("é", "e")
        if chave == "dif" and valor in ("1", "2", "3", "4", "5"):
            campos["dif"] = int(valor)
        elif chave == "prio" and valor in PRIORIDADES:
            campos["prio"] = valor
        elif chave == "prazo" and RE_DATA.fullmatch(valor):
            campos["prazo"] = valor
        texto = texto[:m.start()].rstrip()


def separar_dif(texto):
    texto, campos = separar_campos(texto)
    return texto, campos["dif"]


def montar(prefixo, marca, meio, texto, campos):
    fim = "".join(f" [{k}:: {campos[k]}]" for k in ("dif", "prio", "prazo") if campos.get(k))
    return prefixo + marca + meio + texto + fim


def mexer_tarefas(pedido):
    """Ações da tela: adicionar, marcar, apagar, editar, dificuldade, prioridade, prazo e refazer (o prompt).
    O índice conta só as linhas de tarefa."""
    acao = pedido.get("acao")
    with TRAVA:
        linhas = _ler_linhas()
        if acao == "adicionar":
            texto = " ".join(str(pedido.get("texto", "")).split())[:200]
            if texto:
                linhas.append(f"- [ ] {texto}")
        elif acao in ("marcar", "apagar", "editar", "dificuldade", "prioridade", "prazo", "refazer"):
            alvo, n = int(pedido.get("indice", -1)), -1
            for i, l in enumerate(linhas):
                m = RE_TAREFA.match(l)
                if not m:
                    continue
                n += 1
                if n != alvo:
                    continue
                prefixo, marca, meio = m.group(1), m.group(2), m.group(3)
                texto, campos = separar_campos(m.group(4))
                if acao == "apagar":
                    linhas.pop(i)
                    break
                if acao == "marcar":
                    marca = " " if marca != " " else "x"
                elif acao == "editar":  # texto novo: o Ultron escreve outro prompt (os detalhes são pelo texto)
                    novo = separar_campos(" ".join(str(pedido.get("texto", "")).split())[:200])[0]
                    texto = novo or texto
                elif acao == "dificuldade":
                    nova = int(pedido.get("dif", 0))
                    campos["dif"] = nova if 1 <= nova <= 5 else 0
                elif acao == "prioridade":
                    nova = str(pedido.get("prio", "")).lower()
                    campos["prio"] = nova if nova in PRIORIDADES else ""
                elif acao == "prazo":
                    novo = str(pedido.get("prazo", "")).strip()
                    campos["prazo"] = novo if RE_DATA.fullmatch(novo) else ""
                elif acao == "refazer":  # apaga o prompt guardado; o Ultron escreve outro
                    detalhes = ler_detalhes()
                    if detalhes.pop(texto, None) is not None:
                        salvar_json(DETALHES, detalhes, indent=1)
                if acao == "refazer" or (acao == "dificuldade" and not campos["dif"]) \
                        or (acao == "prioridade" and not campos["prio"]):
                    AVALIACAO["proxima"] = time.time()  # "avaliar de novo": sem esperar a pausa longa
                linhas[i] = montar(prefixo, marca, meio, texto, campos)
                break
        _gravar_linhas(linhas)
    atualizar_tarefas()


def falta_avaliar(x):
    return not x["feita"] and (not x["dif"] or not x["prio"] or not x["prompt"])


def atualizar_tarefas():
    """Relê o tarefas.md (e os detalhes) pro painel e, se faltar algo de alguma pendente, agenda a avaliação."""
    try:
        linhas = arquivo().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        linhas = []
    detalhes = ler_detalhes()
    tarefas = []
    for l in linhas:
        m = RE_TAREFA.match(l)
        if m:
            texto, campos = separar_campos(m.group(4))
            d = detalhes.get(texto) or {}
            tarefas.append({"texto": texto, "feita": m.group(2) != " ", **campos,
                            "tempo": d.get("tempo", ""), "resumo": d.get("resumo", ""), "prompt": d.get("prompt", "")})
    if tarefas != PAINEIS["tarefas"]:
        mudou_lista = PAINEIS["tarefas"] is not None
        PAINEIS["tarefas"] = tarefas
        avisar_paineis()
        if mudou_lista:  # espera a pessoa parar de digitar antes de chamar o Claude
            AVALIACAO["proxima"] = max(AVALIACAO["proxima"], time.time() + 8)
    if any(falta_avaliar(x) for x in tarefas) and not AVALIACAO["rodando"] and time.time() >= AVALIACAO["proxima"]:
        AVALIACAO["rodando"] = True
        threading.Thread(target=avaliar_tarefas, daemon=True).start()


def _pedido(faltando, outras):
    hoje = time.strftime("%Y-%m-%d")
    dia = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][time.localtime().tm_wday]
    lista = {str(n + 1): {"tarefa": x["texto"], "prazo_ja_definido": x["prazo"] or None} for n, x in enumerate(faltando)}
    return (
        f"Você é o Ultron, assistente pessoal do {CFG['nome']}, estudante e programador iniciante. "
        f"Hoje é {dia}, {hoje}. Pra cada tarefa da lista, devolva:\n"
        "- dif: dificuldade de 1 a 5 pelo esforço, tempo e complexidade (1 = muito fácil, minutos; 2 = fácil; "
        "3 = média, uma tarde e exige atenção; 4 = difícil, vários dias ou algo novo de aprender; 5 = muito difícil, "
        "projeto grande, muita incerteza). Use a escala toda.\n"
        '- prio: "alta", "media" ou "baixa", pesando prazo, impacto e o que destrava outras coisas.\n'
        '- prazo: "AAAA-MM-DD" só se o texto da tarefa disser uma data ou um dia (ex.: "até sexta", "dia 20"); '
        'senão "". Não invente prazo.\n'
        '- tempo: estimativa curta de quanto leva, tipo "15 min", "2 h", "1 tarde", "3 dias".\n'
        "- resumo: uma frase dizendo o que é pra fazer e qual é o resultado esperado.\n"
        "- prompt: um prompt completo, em português, que ele vai copiar e colar num assistente de IA (Claude ou "
        "ChatGPT) pra fazer ou aprender a fazer a tarefa. Escreva na primeira pessoa, como se fosse ele pedindo. "
        "Traga o contexto (quem ele é e o nível dele), o objetivo, o que precisa ser entregue e as restrições que dá "
        "pra deduzir, e peça um passo a passo prático; se for de código, peça pra explicar cada parte. O que só ele "
        "sabe fica entre colchetes pra ele completar, tipo [nome do projeto]. Entre 80 e 250 palavras.\n"
        + ("Seja coerente com as notas das outras tarefas: " + json.dumps(outras, ensure_ascii=False) + "\n" if outras else "")
        + "Tarefas, numeradas: " + json.dumps(lista, ensure_ascii=False) + "\n"
        "Não use ferramentas. Responda SOMENTE com um JSON válido (quebras de linha do prompt como \\n), no formato: "
        '{"tarefas":[{"n":1,"dif":3,"prio":"media","prazo":"","tempo":"2 h","resumo":"...","prompt":"..."}]}'
    )


def avaliar_tarefas():
    """Pras pendentes que ainda não têm: dificuldade, prioridade, prazo (se o texto disser), tempo, resumo e prompt.
    Os campos vão pro tarefas.md; o resto pros detalhes. O que você já escolheu à mão nunca é trocado."""
    try:
        todas = PAINEIS["tarefas"] or []
        faltando = [x for x in todas if falta_avaliar(x)][:POR_VEZ]
        if not faltando:
            return
        outras = [f'{x["texto"]} (dificuldade {x["dif"]}, prioridade {x["prio"] or "?"})'
                  for x in todas if not x["feita"] and x["dif"] and x not in faltando][:30]
        resposta = {}
        for item in claude_json(_pedido(faltando, outras), "Read", limite=240).get("tarefas", []):
            try:
                n = int(item.get("n", 0))
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(faltando):
                resposta[faltando[n - 1]["texto"]] = item
        with TRAVA:
            detalhes = ler_detalhes()
            linhas = _ler_linhas()
            existentes = set()
            for i, l in enumerate(linhas):
                m = RE_TAREFA.match(l)
                if not m:
                    continue
                texto, campos = separar_campos(m.group(4))
                existentes.add(texto)
                item = resposta.get(texto)
                if not item:
                    continue
                try:
                    dif = int(item.get("dif", 0))
                except (TypeError, ValueError):
                    dif = 0
                prio = str(item.get("prio", "")).lower().replace("é", "e")
                prazo = str(item.get("prazo") or "").strip()
                if not campos["dif"] and 1 <= dif <= 5:
                    campos["dif"] = dif
                if not campos["prio"] and prio in PRIORIDADES:
                    campos["prio"] = prio
                if not campos["prazo"] and RE_DATA.fullmatch(prazo):
                    campos["prazo"] = prazo
                linhas[i] = montar(m.group(1), m.group(2), m.group(3), texto, campos)
                prompt = str(item.get("prompt", "")).strip()
                if prompt:
                    detalhes[texto] = {"prompt": prompt[:4000], "tempo": str(item.get("tempo", "")).strip()[:30],
                                       "resumo": str(item.get("resumo", "")).strip()[:300],
                                       "quando": time.strftime("%Y-%m-%d")}
            _gravar_linhas(linhas)
            for velho in [t for t in detalhes if t not in existentes]:  # tarefa apagada ou renomeada
                detalhes.pop(velho)
            salvar_json(DETALHES, detalhes, indent=1)
        log({"evento": "tarefas_avaliadas", "avaliadas": len(resposta)})
        AVALIACAO["proxima"] = time.time() + (20 if resposta else 600)
    except Exception as erro:
        log_erro("paineis_falhou", erro, onde="tarefas")
        AVALIACAO["proxima"] = time.time() + 600  # falhou: tenta de novo em 10 min
    finally:
        AVALIACAO["rodando"] = False
        atualizar_tarefas()
