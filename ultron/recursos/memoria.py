"""A memória do Ultron: o que você pede pra ele guardar ("lembra que minha namorada se chama Ana").

Fica em <sua pasta>/memoria.md, uma seção por assunto e uma lembrança por linha, num formato que o Obsidian também
abre (dá pra editar à mão). A barra mostra como um grafo: você no meio, os assuntos em volta, cada lembrança ligada
ao assunto dela e a quem ela cita. O Claude recebe tudo ao abrir (veja para_o_prompt).
"""
import hashlib
import re
import threading
import time

from ..nucleo.config import CFG
from ..nucleo.eventos import EVENTOS
from ..nucleo.texto import normalizar

TRAVA = threading.Lock()
OUTRAS = "Outras coisas"
ASSUNTOS = {  # assunto -> palavras sem acento que puxam a lembrança pra ele (de 4 letras pra cima, vale o começo)
    "Pessoas": ("namorad", "noiv", "esposa", "marido", "mae", "pai", "irma", "irmao", "filh", "amig", "chama",
                "aniversar", "familia", "primo", "prima", "tio", "tia", "avo", "avos", "sogr", "cunhad", "chefe",
                "colega", "conhec"),
    "Trabalho e estudo": ("trabalh", "empresa", "emprego", "faculdade", "curso", "prova", "aula", "aulas", "projeto",
                          "cliente", "reuniao", "estag", "escola", "materia", "cnpj", "empreend", "negocio", "loja",
                          "venda"),
    "Gostos": ("gost", "prefer", "favorit", "odei", "ama", "amo", "curte", "curti", "time", "comida", "musica", "filme",
               "serie", "jogo", "banda", "cantor"),
    "Casa e rotina": ("acord", "dorm", "casa", "rotina", "academia", "trein", "remedio", "carro", "endereco", "mora",
                      "cachorr", "gato", "gata", "pet", "senha", "wifi", "dieta"),
}
CABECALHO = ("# Memória do Ultron\n\nO que o {nome} pediu pro Ultron guardar. Uma lembrança por linha "
             "(dá pra editar à mão; o Ultron lê ao abrir).\n")
LINHA = re.compile(r"^- (.+?)(?: · (\d{4}-\d{2}-\d{2}))?\s*$")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
NAO_SAO_NOMES = {"Ultron", "Eu", "Ele", "Ela", "Meu", "Minha", "Seu", "Sua", "Não", "Sim", "Quando", "Hoje"}
LIMITE_DE_TEXTO = 300


def arquivo():
    return CFG["pasta"] / "memoria.md"


def _id(texto):
    return hashlib.sha1(" ".join(normalizar(texto)).encode()).hexdigest()[:8]


def ler():
    """As lembranças, na ordem do arquivo: [{id, texto, assunto, quando}]."""
    try:
        linhas = arquivo().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    lembrancas, assunto = [], OUTRAS
    for linha in linhas:
        if linha.startswith("## "):
            assunto = linha[3:].strip() or OUTRAS
        elif (achou := LINHA.match(linha.strip())):
            texto = achou.group(1).strip()
            lembrancas.append({"id": _id(texto), "texto": texto, "assunto": assunto, "quando": achou.group(2) or ""})
    return lembrancas


def _gravar(lembrancas):
    por_assunto = {}
    for item in lembrancas:
        por_assunto.setdefault(item["assunto"], []).append(item)
    partes = [CABECALHO.format(nome=CFG["nome"])]
    for assunto, itens in por_assunto.items():
        partes.append(f"## {assunto}")
        partes.extend(f"- {i['texto']}" + (f" · {i['quando']}" if i["quando"] else "") for i in itens)
        partes.append("")
    arquivo().parent.mkdir(parents=True, exist_ok=True)
    arquivo().write_text("\n".join(partes), encoding="utf-8")
    EVENTOS.emitir({"tipo": "memoria"})


def assunto_de(texto):
    """Pessoas, Trabalho e estudo, Gostos, Casa e rotina ou Outras coisas, pelas palavras da lembrança."""
    palavras = normalizar(texto)
    for assunto, chaves in ASSUNTOS.items():
        if any(p == c or (len(c) >= 4 and p.startswith(c)) for p in palavras for c in chaves):
            return assunto
    return OUTRAS


def guardar(texto, assunto=""):
    """Guarda uma lembrança nova (ou devolve a que já existe igual). ValueError se vier vazia ou grande demais."""
    texto = re.sub(r"\s+", " ", texto or "").strip().rstrip(".").strip()
    if not texto:
        raise ValueError("O que é pra guardar?")
    if len(texto) > LIMITE_DE_TEXTO:
        raise ValueError(f"Lembrança grande demais (máximo {LIMITE_DE_TEXTO} letras). Isso cabe melhor numa nota.")
    texto = texto[0].upper() + texto[1:]
    with TRAVA:
        lembrancas = ler()
        igual = next((i for i in lembrancas if i["id"] == _id(texto)), None)
        if igual:
            return igual
        nova = {"id": _id(texto), "texto": texto, "assunto": (assunto or "").strip() or assunto_de(texto),
                "quando": time.strftime("%Y-%m-%d")}
        _gravar(lembrancas + [nova])
    return nova


def apagar(id_lembranca):
    """Tira uma lembrança. ValueError se ela não existe."""
    with TRAVA:
        lembrancas = ler()
        restantes = [i for i in lembrancas if i["id"] != id_lembranca]
        if len(restantes) == len(lembrancas):
            raise ValueError("Essa lembrança não existe mais.")
        _gravar(restantes)


def procurar(trecho):
    """As lembranças que contêm todas as palavras do trecho (sem ligar pra acento)."""
    palavras = normalizar(trecho)
    return [i for i in ler() if all(p in " ".join(normalizar(i["texto"])) for p in palavras)]


def nomes_citados(texto):
    """Quem a lembrança cita: os [[links]] e as palavras com letra maiúscula no meio da frase."""
    citados = {m.strip() for m in LINK.findall(texto)}
    for frase in re.split(r"[.!?]\s+", LINK.sub("", texto)):
        palavras = re.findall(r"[\wÀ-ÿ]+", frase)[1:]  # a primeira da frase é maiúscula de qualquer jeito
        citados |= {p for p in palavras if len(p) >= 3 and p[0].isupper() and p not in NAO_SAO_NOMES}
    return citados


def grafo():
    """Nós e ligações do grafo, como no Obsidian: você -> assuntos -> lembranças -> nomes citados em mais de uma."""
    lembrancas = ler()
    nos = [{"id": "voce", "nome": CFG["nome"], "tipo": "centro"}]
    ligacoes = []
    for assunto in dict.fromkeys(i["assunto"] for i in lembrancas):
        nos.append({"id": "assunto:" + assunto, "nome": assunto, "tipo": "assunto"})
        ligacoes.append(["voce", "assunto:" + assunto])
    citacoes = {}
    for item in lembrancas:
        nos.append({"id": item["id"], "nome": item["texto"], "tipo": "lembranca", "assunto": item["assunto"]})
        ligacoes.append(["assunto:" + item["assunto"], item["id"]])
        for nome in nomes_citados(item["texto"]):
            citacoes.setdefault(nome, []).append(item["id"])
    for nome, ids in citacoes.items():
        if len(ids) > 1 or any(f"[[{nome}" in i["texto"] for i in lembrancas if i["id"] in ids):
            nos.append({"id": "nome:" + nome, "nome": nome, "tipo": "nome"})
            ligacoes.extend([i, "nome:" + nome] for i in ids)
    return {"nos": nos, "ligacoes": ligacoes}


def para_o_prompt(limite=80):
    """As lembranças em texto, pro Claude (e as outras IAs) saberem desde o começo da conversa."""
    lembrancas = ler()[-limite:]
    linhas = "\n".join(f"- {i['texto']} ({i['assunto'].lower()})" for i in lembrancas) or "(nada guardado ainda)"
    return (f"\n\n## O que você lembra dele\nFica em `{arquivo()}` (pra guardar algo novo, acrescente uma linha "
            f"`- texto` na seção certa desse arquivo):\n{linhas}")
