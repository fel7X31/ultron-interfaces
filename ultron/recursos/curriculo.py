"""Currículo: analisar (conselhos do Claude, você edita) e adaptar (o Claude reescreve com você, pergunta e dá ideias).

A tela fica em web/curriculo.html. Aqui ficam o upload (PDF ou Word), a conversa com o Claude (sai aos poucos, em
NDJSON, pra tela mostrar ele escrevendo) e a exportação pra Word (.docx feito na mão) e PDF (Edge/Chrome headless).

O currículo é guardado num Markdown simples: "# Nome", linha de contato, "## Seção", "### Cargo | Empresa | período",
"- item" e **negrito**. A tela, o Word e o PDF saem desse mesmo texto.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree

CTX = {}
TRAVA = threading.Lock()
RODANDO = {"agora": False}

FORMATO = """
## Formato do currículo
Sempre escreva o currículo neste Markdown simples, sem tabelas, sem emoji, sem HTML:
# Nome Completo
Cidade, UF · telefone · e-mail · LinkedIn (uma linha só, separada por " · ")
## Nome da seção
Parágrafo curto (ex.: resumo profissional).
### Cargo | Empresa | mês/ano a mês/ano
- conquista ou responsabilidade, começando com verbo, com número quando houver
Use **negrito** só pra destacar pouca coisa. Seções comuns: Resumo profissional, Experiência, Formação,
Habilidades, Idiomas, Cursos e certificações, Projetos. Nunca invente fato, número, empresa ou data: quando faltar
informação, escreva um marcador entre colchetes, ex.: [quantos clientes você atendia?], e pergunte.

## Aparência da folha (você controla)
Você decide a aparência da folha, e ela vale na tela, no Word e no PDF exportados. Nunca diga que não pode mudar fonte,
tamanho, cor ou espaçamento, nem mande ele pedir pra outra pessoa: faça você. Quando ele pedir uma mudança visual (ou
quando ajudar, ex.: apertar pra caber em 1 página), escreva a tag abaixo SÓ com as chaves que mudam:
<estilo>{{"fonte": "times", "tamanho": 11, "cor": "#1f2a44", "espacamento": "compacto", "nome_alinhado": "esquerda", "linhas": true, "maiusculas": true}}</estilo>
- fonte: calibri (padrão), arial, segoe, verdana (sem serifa) | times, georgia, garamond, cambria (com serifa)
- tamanho: do texto, de 8 a 20 (padrão 10.5). Nome e títulos crescem junto.
- cor: dos títulos das seções e das linhas, em hexadecimal (padrão #1f2a44, azul-marinho; preto é #111111)
- espacamento: compacto | normal | amplo
- nome_alinhado: centro | esquerda (vale pro nome e a linha de contato)
- texto_alinhado: esquerda | justificado (parágrafos e itens)
- linhas: true/false (linha embaixo do título de cada seção)
- maiusculas: true/false (títulos das seções em maiúsculas)
Se ele quiser "a fonte do original", olhe o arquivo original e escolha a mais parecida (serifada estilo Times = times).
Se for só mudança visual, não precisa reenviar o <curriculo>: mande <estilo> e uma <mensagem> curta dizendo o que mudou.
Recuo: 2 espaços no começo de um item, parágrafo ou cargo = 1 nível pra direita (até 3 níveis, ex.: "  - subitem").
Linha em branco: uma linha só com &nbsp; vira um espaço vazio na folha (empurra o que vem depois pra baixo).
Linha separadora: uma linha só com --- no currículo vira uma linha horizontal igual à que fica embaixo do título das
seções (mesma cor e espessura). Use pra separar experiências ou blocos quando ele pedir.
Ele também pode editar a folha direto, clicando nela; a "versão atual da folha" que chega nas mensagens já traz as
edições dele: respeite o que ele mudou.
IMPORTANTE: se em respostas antigas desta conversa você disse que não podia mudar fonte, alinhamento, linhas ou cor, ou
mandou ele pedir pra outro assistente, isso NÃO vale mais: agora você pode e deve fazer, com <estilo> e ---. Não existe
"Jarvis" aqui: quem cuida do currículo é você, Ultron.
"""

FONTES = {
    "calibri": ("Calibri, Carlito, 'Segoe UI', Arial, sans-serif", "Calibri"),
    "arial": ("Arial, Helvetica, sans-serif", "Arial"),
    "segoe": ("'Segoe UI', Arial, sans-serif", "Segoe UI"),
    "verdana": ("Verdana, Geneva, sans-serif", "Verdana"),
    "times": ("'Times New Roman', Times, serif", "Times New Roman"),
    "georgia": ("Georgia, 'Times New Roman', serif", "Georgia"),
    "garamond": ("Garamond, 'EB Garamond', 'Times New Roman', serif", "Garamond"),
    "cambria": ("Cambria, Georgia, serif", "Cambria"),
}
ESPACOS = {"compacto": (0.7, 1.25, 257), "normal": (1.0, 1.38, 283), "amplo": (1.35, 1.5, 308)}
ESTILO_PADRAO = {"fonte": "calibri", "tamanho": 10.5, "cor": "#1f2a44", "espacamento": "normal",
                 "nome_alinhado": "centro", "texto_alinhado": "esquerda", "linhas": True, "maiusculas": True}


def normalizar_estilo(*partes):
    """Junta estilos (o último ganha) e corrige valores inválidos."""
    est = dict(ESTILO_PADRAO)
    for parte in partes:
        if isinstance(parte, dict):
            est.update({k: v for k, v in parte.items() if k in ESTILO_PADRAO})
    fonte = str(est["fonte"]).lower().strip()
    fonte = next((k for k in FONTES if k in fonte or fonte in FONTES[k][1].lower()), "calibri")
    try:
        tam = min(20.0, max(8.0, float(est["tamanho"])))
    except (TypeError, ValueError):
        tam = 10.5
    cor = str(est["cor"]).strip()
    cor = cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else ESTILO_PADRAO["cor"]
    esp = est["espacamento"] if est["espacamento"] in ESPACOS else "normal"
    alinh = "esquerda" if str(est["nome_alinhado"]).startswith("esq") else "centro"
    texto = "justificado" if str(est["texto_alinhado"]).startswith("just") else "esquerda"
    return {"fonte": fonte, "tamanho": tam, "cor": cor.lower(), "espacamento": esp, "nome_alinhado": alinh,
            "texto_alinhado": texto, "linhas": bool(est["linhas"]), "maiusculas": bool(est["maiusculas"])}


def css_estilo(est):
    """Variáveis CSS da folha (curriculo-folha.css usa elas)."""
    est = normalizar_estilo(est)
    mult, linha, _ = ESPACOS[est["espacamento"]]
    return (f"--cv-fonte: {FONTES[est['fonte']][0]}; --cv-tam: {est['tamanho']}pt; --cv-cor: {est['cor']}; "
            f"--cv-esp: {mult}; --cv-linha: {linha}; --cv-alinh: {'left' if est['nome_alinhado'] == 'esquerda' else 'center'}; "
            f"--cv-borda: {'1.2px' if est['linhas'] else '0px'}; --cv-caixa: {'uppercase' if est['maiusculas'] else 'none'}; "
            f"--cv-texto-alinh: {'justify' if est['texto_alinhado'] == 'justificado' else 'left'};")


def salvar_estilo(modo, estilo):
    """A barra de edição da tela muda a aparência (fonte, tamanho, cor...) e grava aqui."""
    if modo not in ("analisar", "adaptar"):
        raise ValueError("modo inválido")
    with TRAVA:
        est = ler_estado()
        e = est.setdefault(modo, {})
        e["estilo"] = normalizar_estilo(e.get("estilo"), estilo)
        salvar_estado(est)
    return {"estilo": e["estilo"], "estilo_css": css_estilo(e["estilo"])}


def _ler_estilo(bruto):
    try:
        return json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
    except ValueError:
        return None

SISTEMA = """Seu nome aqui é Ultron, o assistente do {nome} (se se referir a si mesmo, diga Ultron, nunca Claude). Você é um especialista em recrutamento e em currículos no Brasil, ajudando {nome} a atualizar o currículo
porque ele está procurando um novo emprego. Seja direto, prático e humano. Português do Brasil.
Nunca mencione demissão no currículo. Pense em ATS (sistemas de triagem): palavras-chave da área, títulos claros,
sem colunas nem gráficos. Ideal: 1 página (2 no máximo, se tiver muita experiência).
O arquivo original dele está na pasta atual (use a ferramenta Read só pra ler esse arquivo).

## Vagas de emprego
Quando ele mandar um link de vaga (LinkedIn, Gupy, Indeed, Catho, InfoJobs, site da empresa...), abra com WebFetch e
leia a vaga inteira: cargo, empresa, requisitos obrigatórios, desejáveis, palavras-chave, senioridade, modelo
(remoto/híbrido/presencial) e local. Se ele colar o texto da vaga, use o texto. Se a página pedir login ou não abrir,
diga isso em uma frase e peça pra ele colar o texto da vaga (não invente o conteúdo). WebSearch só pra conhecer a empresa.
Com a vaga lida, compare com o currículo: o quanto ele encaixa (0 a 100%), o que já atende, o que falta e quais
palavras-chave da vaga faltam no currículo. Use isso pra adaptar o currículo àquela vaga, sem inventar experiência: o
que ele não tem vira pergunta ("você já usou X?") ou sugestão de como aprender, nunca vira linha falsa no currículo.
""" + FORMATO

ADAPTAR = """
## Modo: adaptar currículo
Vocês constroem juntos uma nova versão do currículo, numa folha em branco ao lado do original.
Em toda resposta escreva, nesta ordem:
<mensagem>
O que você mudou e por quê (bem curto) e, no fim, de 1 a 3 perguntas objetivas ou ideias pra complementar
(conquistas com número, ferramentas, cursos, vaga alvo...). Numere as perguntas. Até umas 120 palavras, texto
simples, sem Markdown.
</mensagem>
<curriculo>
o currículo COMPLETO atualizado, no formato acima
</curriculo>
Se a mensagem dele não pedir mudança no currículo (ex.: só uma dúvida), responda só a <mensagem>
(mais o <estilo>, se for mudança visual).
"""

ANALISAR = """
## Modo: analisar currículo
Você analisa o currículo e dá conselhos; quem edita é ele, na própria folha.
Na primeira resposta (e sempre que ele pedir pra reanalisar) escreva, nesta ordem:
<estilo>(só na primeira resposta) a aparência do original: fonte mais parecida (com serifa estilo Times = times),
tamanho do texto, nome_alinhado, e "linhas": false se os títulos do original não têm linha embaixo</estilo>
<folha>
(só na primeira resposta, e só se o pedido disser pra montar a folha) uma CÓPIA FIEL do layout do arquivo original em
HTML, pra ele editar em cima: mesmo texto, mesma ordem, mesmas quebras de linha, nada melhorado nem resumido. Use só:
<h1> pro nome; <div> pra cada linha comum (uma linha do original = um <div>; linha em branco = <div><br></div>);
<b>, <i>, <u> como no original (título de seção que no original é só negrito fica <div><b>Título</b></div>, sem <h2>);
<ul><li> pra listas com marcador (recuo: class="r1", "r2" ou "r3"); <hr> onde o original tem uma linha horizontal;
class="r1"/"r2"/"r3" num <div> recuado. Nada de style, tabela, imagem ou link.
</folha>
<analise>
um JSON válido: {{"nota": 0 a 10, "resumo": "duas frases sobre o currículo",
"pontos_fortes": ["..."], "conselhos": [{{"titulo": "curto", "secao": "seção do currículo ou Geral",
"prioridade": "alta|media|baixa", "detalhe": "o que está ruim e como melhorar",
"exemplo": "texto pronto sugerido, quando fizer sentido, senão vazio"}}]}}
Ordene os conselhos por prioridade. Entre 5 e 12 conselhos, concretos, citando o trecho do currículo.
</analise>
<mensagem>
uma frase curta convidando ele a editar ou perguntar
</mensagem>
Se ele só fizer uma pergunta, responda só a <mensagem> (até umas 150 palavras, texto simples, sem Markdown).
Se ele pedir mudança visual na folha dele, mande o <estilo> e uma <mensagem> curta (o texto da folha é ele quem edita).
Nunca reescreva a folha dele depois da primeira resposta: dê o texto sugerido no conselho ou na mensagem.
"""


def iniciar(pasta, estado, nome, log, web):
    CTX.update(pasta=Path(pasta), estado=Path(estado) / "curriculo", nome=nome, log=log, web=Path(web))
    CTX["estado"].mkdir(parents=True, exist_ok=True)



def _arq_estado():
    return CTX["estado"] / "estado.json"


def ler_estado():
    try:
        return json.loads(_arq_estado().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def salvar_estado(est):
    _arq_estado().write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


def estado_publico():
    est = ler_estado()
    modos = {}
    for m in ("analisar", "adaptar"):
        e = est.get(m) or {}
        estilo = normalizar_estilo(e.get("estilo"))
        modos[m] = {"curriculo": e.get("curriculo", ""), "analise": e.get("analise"),
                    "conversa": e.get("conversa", [])[-60:], "estilo": estilo, "estilo_css": css_estilo(estilo),
                    "html": e.get("html", "") if e.get("html") and e.get("html_md") == e.get("curriculo") else ""}
    orig = est.get("original") or {}
    return {"original": {"nome": orig.get("nome", ""), "tipo": orig.get("tipo", ""), "html": orig.get("html", "")},
            "modos": modos, "rodando": RODANDO["agora"]}



def _texto_docx(dados):
    """Tira os parágrafos de um .docx (só biblioteca padrão). Devolve (texto, html)."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(_bytes_io(dados)) as z:
        raiz = ElementTree.fromstring(z.read("word/document.xml"))
    linhas, partes = [], []
    for p in raiz.iter(ns + "p"):
        runs = []
        for r in p.iter(ns + "r"):
            t = "".join((x.text or "") if x.tag == ns + "t" else ("\t" if x.tag == ns + "tab" else "")
                        for x in r if x.tag in (ns + "t", ns + "tab"))
            if t:
                negrito = r.find(f"{ns}rPr/{ns}b") is not None
                runs.append((t, negrito))
        texto = "".join(t for t, _ in runs).strip()
        if not texto:
            continue
        estilo = p.find(f"{ns}pPr/{ns}pStyle")
        estilo = (estilo.get(ns + "val") if estilo is not None else "") or ""
        lista = p.find(f"{ns}pPr/{ns}numPr") is not None
        corpo = "".join(f"<b>{html.escape(t)}</b>" if b else html.escape(t) for t, b in runs)
        if lista:
            linhas.append("- " + texto)
            partes.append(f"<li>{corpo}</li>")
        elif estilo.lower().startswith(("heading", "título", "titulo", "title")):
            linhas.append("## " + texto)
            partes.append(f"<h3>{corpo}</h3>")
        else:
            linhas.append(texto)
            partes.append(f"<p>{corpo}</p>")
    corpo_html = re.sub(r"((?:<li>.*?</li>)+)", r"<ul>\1</ul>", "".join(partes))
    return "\n".join(linhas), corpo_html


def _docx_para_folha(dados):
    """Monta a folha a partir do Word: mesmas linhas, negrito/itálico/sublinhado, quebras, listas, recuos e linhas
    horizontais (borda de parágrafo). Também chuta a aparência (fonte, tamanho, nome centralizado). Devolve (html, estilo)."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    w = lambda nome: ns + nome
    with zipfile.ZipFile(_bytes_io(dados)) as z:
        raiz = ElementTree.fromstring(z.read("word/document.xml"))
        try:
            estilos = ElementTree.fromstring(z.read("word/styles.xml"))
        except KeyError:
            estilos = None

    def ligado(rpr, nome):
        x = rpr.find(w(nome)) if rpr is not None else None
        return x is not None and (x.get(w("val")) or "true").lower() not in ("0", "false", "none")

    tam_padrao = 11.0
    if estilos is not None:
        sz = estilos.find(f".//{w('rPrDefault')}//{w('sz')}")
        if sz is not None and (sz.get(w("val")) or "").isdigit():
            tam_padrao = int(sz.get(w("val"))) / 2
    fontes, tamanhos, paragrafos = {}, {}, []
    corpo = raiz.find(w("body"))
    for p in (corpo.iter(w("p")) if corpo is not None else []):
        ppr = p.find(w("pPr"))
        pedacos, maior = [], 0
        for r in p.iter(w("r")):
            rpr = r.find(w("rPr"))
            b, i = ligado(rpr, "b"), ligado(rpr, "i")
            u = rpr is not None and rpr.find(w("u")) is not None and (rpr.find(w("u")).get(w("val")) or "single") != "none"
            if rpr is not None:
                f = rpr.find(w("rFonts"))
                nome_fonte = f is not None and (f.get(w("ascii")) or f.get(w("hAnsi")))
                sz = rpr.find(w("sz"))
                tam = int(sz.get(w("val"), "0")) / 2 if sz is not None and (sz.get(w("val")) or "").isdigit() else 0
            else:
                nome_fonte, tam = None, 0
            tam = tam or tam_padrao
            for x in r:
                if x.tag == w("t") and x.text:
                    pedacos.append((x.text, b, i, u))
                    if nome_fonte:
                        fontes[nome_fonte] = fontes.get(nome_fonte, 0) + len(x.text)
                    if tam:
                        tamanhos[tam] = tamanhos.get(tam, 0) + len(x.text)
                        maior = max(maior, tam)
                elif x.tag == w("tab"):
                    pedacos.append(("    ", b, i, u))
                elif x.tag in (w("br"), w("cr")):
                    pedacos.append(("BR", 0, 0, 0))
        estilo_p = ppr.find(w("pStyle")).get(w("val"), "") if ppr is not None and ppr.find(w("pStyle")) is not None else ""
        num = ppr.find(w("numPr")) if ppr is not None else None
        nivel = 0
        if num is not None and num.find(w("ilvl")) is not None:
            nivel = int(num.find(w("ilvl")).get(w("val"), "0") or 0)
        ind = ppr.find(w("ind")) if ppr is not None else None
        esquerda = int((ind.get(w("left")) or ind.get(w("start")) or "0").lstrip("-") or 0) if ind is not None else 0
        jc = ppr.find(w("jc")).get(w("val"), "") if ppr is not None and ppr.find(w("jc")) is not None else ""
        borda = ppr is not None and ppr.find(f"{w('pBdr')}/{w('bottom')}") is not None
        paragrafos.append({"pedacos": pedacos, "estilo": estilo_p.lower(), "lista": num is not None, "nivel": nivel,
                           "esquerda": esquerda, "jc": jc, "borda": borda, "maior": maior})

    fonte_doc = max(fontes, key=fontes.get) if fontes else ""
    if not fonte_doc and estilos is not None:
        f = estilos.find(f".//{w('rPrDefault')}//{w('rFonts')}")
        fonte_doc = f.get(w("ascii")) if f is not None else ""
    tam_doc = tam_padrao
    if tamanhos:
        metade, soma = sum(tamanhos.values()) / 2, 0
        for t in sorted(tamanhos):
            soma += tamanhos[t]
            if soma >= metade:
                tam_doc = t
                break

    def inline(pedacos):
        out = []
        for t, b, i, u in pedacos:
            if t == "BR":
                out.append("<br>")
                continue
            x = html.escape(t, quote=False)
            if u:
                x = f"<u>{x}</u>"
            if i:
                x = f"<i>{x}</i>"
            if b:
                x = f"<b>{x}</b>"
            out.append(x)
        return "".join(out).replace("</b><b>", "").replace("</i><i>", "").replace("</u><u>", "")

    partes, lista_aberta, nome_feito, nome_centro = [], False, False, False
    for par in paragrafos:
        texto = "".join(t for t, *_ in par["pedacos"] if t != "BR").strip()
        conteudo = inline(par["pedacos"])
        if par["lista"] and texto:
            if not lista_aberta:
                partes.append("<ul>")
                lista_aberta = True
            r = min(3, par["nivel"])
            partes.append(("<li class='r%d'>" % r if r else "<li>") + conteudo + "</li>")
            continue
        if lista_aberta:
            partes.append("</ul>")
            lista_aberta = False
        if not texto:
            partes.append("<hr>" if par["borda"] else "<div><br></div>")
            continue
        e_titulo = par["estilo"].startswith(("title", "título", "titulo"))
        e_nome = not nome_feito and (e_titulo or (tam_doc and par["maior"] >= tam_doc * 1.4))
        if e_nome:
            nome_feito, nome_centro = True, par["jc"] == "center"
            partes.append(f"<h1>{inline([(t, 0, i, u) for t, b, i, u in par['pedacos']])}</h1>")
        elif par["estilo"].startswith(("heading1", "heading 1", "título1", "titulo1")):
            partes.append(f"<h2>{conteudo}</h2>")
        elif par["estilo"].startswith(("heading", "título", "titulo")):
            partes.append(f"<h3>{conteudo}</h3>")
        else:
            r = min(3, round(par["esquerda"] / 425))
            partes.append(("<div class='r%d'>" % r if r else "<div>") + conteudo + "</div>")
        nome_feito = nome_feito or bool(texto)
        if par["borda"]:
            partes.append("<hr>")
    if lista_aberta:
        partes.append("</ul>")
    estilo = {"fonte": fonte_doc or "calibri", "tamanho": tam_doc or 10.5, "nome_alinhado": "centro" if nome_centro else "esquerda",
              "linhas": False, "maiusculas": False}
    return sanear_html("".join(partes))[0], estilo


def md_de_arvore(arvore):
    """Folha (árvore do HTML) -> o Markdown simples que o Ultron lê. Cada linha da folha vira uma linha."""
    linhas = []

    def texto_inline(no):
        if isinstance(no, str):
            return re.sub(r"\s+", " ", no)
        if no["tag"] == "br":
            return "\n"
        dentro = "".join(texto_inline(f) for f in no["filhos"] if not (isinstance(f, dict) and f["tag"] in ("ul", "ol")))
        if no["tag"] in ("b", "strong") and dentro.strip():
            return f"**{dentro.strip()}** "
        if no["tag"] in ("i", "em") and dentro.strip():
            return f"*{dentro.strip()}* "
        return dentro

    def recuo(no):
        return "  " * next((int(c[1]) for c in no["cls"] if c in ("r1", "r2", "r3")), 0)

    def blocos(no):
        for f in no["filhos"]:
            if isinstance(f, str):
                if f.strip():
                    linhas.append(f.strip())
                continue
            t = f["tag"]
            if t == "hr":
                linhas.extend(["", "---", ""])
            elif t == "h1":
                linhas.append("# " + texto_inline(f).strip())
            elif t == "h2":
                linhas.extend(["", "## " + texto_inline(f).strip()])
            elif t == "h3":
                linhas.append(recuo(f) + "### " + texto_inline(f).strip())
            elif t in ("ul", "ol"):
                for li in f["filhos"]:
                    if isinstance(li, dict) and li["tag"] == "li":
                        linhas.append(recuo(li) + "- " + texto_inline(li).strip())
                        for sub in li["filhos"]:
                            if isinstance(sub, dict) and sub["tag"] in ("ul", "ol"):
                                blocos({"filhos": [sub]})
            elif any(isinstance(x, dict) and x["tag"] in _BLOCOS for x in f["filhos"]):
                blocos(f)
            else:
                partes = [x.strip() for x in texto_inline(f).split("\n")]
                if not any(partes):
                    linhas.append("&nbsp;")
                for x in partes:
                    if x:
                        linhas.append(recuo(f) + x)

    blocos(arvore)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def _bytes_io(dados):
    import io
    return io.BytesIO(dados)


def receber_arquivo(nome, dados):
    nome = re.sub(r"[^\w .()-]", "_", nome or "curriculo")[:80]
    ext = Path(nome).suffix.lower()
    if ext not in (".pdf", ".docx"):
        if ext == ".doc":
            raise ValueError("Arquivo .doc antigo: abra no Word e salve como .docx (ou PDF).")
        raise ValueError("Use um PDF ou um Word (.docx).")
    if len(dados) > 15 * 1024 * 1024:
        raise ValueError("Arquivo grande demais (máximo 15 MB).")
    with TRAVA:
        pasta = CTX["estado"]
        for velho in pasta.glob("original.*"):
            velho.unlink()
        (pasta / "texto-original.txt").unlink(missing_ok=True)
        (pasta / ("original" + ext)).write_bytes(dados)
        orig = {"nome": nome, "tipo": ext[1:], "html": ""}
        if ext == ".docx":
            try:
                texto, corpo = _texto_docx(dados)
            except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
                raise ValueError("Não consegui ler esse Word. Tente salvar como PDF.")
            (pasta / "texto-original.txt").write_text(texto, encoding="utf-8")
            orig["html"] = corpo
        est = ler_estado()
        est["original"] = orig
        for m in ("analisar", "adaptar"):
            est[m] = {}
        if ext == ".docx":
            try:
                folha, estilo = _docx_para_folha(dados)
                md = md_de_arvore(sanear_html(folha)[1])
                if md.strip():
                    est["analisar"] = {"curriculo": md, "html": folha, "html_md": md, "estilo": normalizar_estilo(estilo)}
                    orig["html"] = folha
            except Exception as erro:
                CTX["log"]({"evento": "curriculo_falhou", "detalhe": "docx->folha " + repr(erro)[:200]})
        salvar_estado(est)
    return estado_publico()


def caminho_original():
    tipo = (ler_estado().get("original") or {}).get("tipo")
    p = CTX["estado"] / f"original.{tipo}" if tipo else None
    return p if p and p.exists() else None


def fechar_arquivo():
    """Tira o currículo aberto: apaga o original e as duas conversas (os exportados na pasta continuam)."""
    if RODANDO["agora"]:
        raise ValueError("Espere o Ultron terminar antes de fechar o arquivo.")
    with TRAVA:
        for velho in CTX["estado"].glob("original.*"):
            velho.unlink()
        (CTX["estado"] / "texto-original.txt").unlink(missing_ok=True)
        salvar_estado({})
    return estado_publico()


def recomecar(modo):
    with TRAVA:
        est = ler_estado()
        if modo in ("analisar", "adaptar"):
            est[modo] = {}
        salvar_estado(est)
    return estado_publico()


def guardar_edicao(modo, curriculo, html_folha_editada=None):
    """Você edita a folha: a tela manda o texto (pro Ultron) e o HTML (o layout exato que você montou)."""
    with TRAVA:
        est = ler_estado()
        e = est.setdefault(modo, {})
        e["curriculo"] = str(curriculo)[:40000]
        if html_folha_editada:
            e["html"], e["html_md"] = sanear_html(html_folha_editada)[0], e["curriculo"]
        salvar_estado(est)



def _partes(texto):
    """Separa <mensagem>, <curriculo> e <analise>, mesmo com a tag ainda aberta (no meio da escrita)."""
    saida = {}
    for tag in ("mensagem", "curriculo", "analise", "estilo", "folha"):
        m = re.search(rf"<{tag}>\s*(.*?)(?:</{tag}>|$)", texto, re.S)
        if m:
            saida[tag] = m.group(1).rstrip()
            saida[tag + "_fechou"] = f"</{tag}>" in texto[m.start():]
    return saida


def _arquivo_para_claude():
    pasta = CTX["estado"]
    if (pasta / "texto-original.txt").exists():
        return "texto-original.txt"
    p = caminho_original()
    return p.name if p else ""


def conversar(modo, mensagem, curriculo_atual, escrever, html_atual=None):
    """Roda o Claude e chama escrever(dict) a cada pedaço. Devolve no fim."""
    if modo not in ("analisar", "adaptar"):
        raise ValueError("modo inválido")
    if RODANDO["agora"]:
        raise ValueError("O Ultron ainda está respondendo. Espere ele terminar.")
    arquivo = _arquivo_para_claude()
    if not arquivo:
        raise ValueError("Abra ou arraste o seu currículo primeiro.")
    RODANDO["agora"] = True
    try:
        return _conversar(modo, mensagem, curriculo_atual, escrever, arquivo, html_atual)
    finally:
        RODANDO["agora"] = False


def _conversar(modo, mensagem, curriculo_atual, escrever, arquivo, html_atual=None):
    est = ler_estado()
    e = est.get(modo) or {}
    primeira = not e.get("sessao")
    if curriculo_atual is not None and (modo == "analisar" or e.get("curriculo")):
        e["curriculo"] = str(curriculo_atual)[:40000]
    pedido = mensagem.strip()
    if primeira:
        if modo == "adaptar":
            abertura = (f"Leia o meu currículo original no arquivo {arquivo}. Escreva a primeira versão melhorada e me "
                        "pergunte o que falta pra deixar ele forte.")
        else:
            if e.get("curriculo"):
                abertura = (f"Leia o meu currículo original no arquivo {arquivo} e faça a análise completa com conselhos. "
                            "A folha já foi montada direto do meu Word, igual ao original: NÃO escreva <folha> nem "
                            "<curriculo> e não mande <estilo>. O texto da folha:\n" + e["curriculo"])
            else:
                abertura = (f"Leia o meu currículo original no arquivo {arquivo} (olhe o layout das páginas), monte a "
                            "<folha> como cópia fiel dele e faça a análise completa com conselhos.")
        pedido = abertura + ("\n\nO que eu disse: " + pedido if pedido else "")
    elif modo == "analisar" and curriculo_atual is not None:
        pedido = (pedido or "Reanalise.") + "\n\nO currículo como está agora na folha (editado por mim):\n" + e["curriculo"]
    elif modo == "adaptar" and e.get("curriculo"):
        pedido += "\n\n(Versão atual da folha, com as edições que ele fez à mão; parta dela:)\n" + e["curriculo"]

    sistema = SISTEMA.format(nome=CTX["nome"]) + (ADAPTAR if modo == "adaptar" else ANALISAR.replace("{{", "{").replace("}}", "}"))
    sessao = e.get("sessao") or str(uuid.uuid4())
    cmd = [shutil.which("claude") or "claude", "-p", pedido, "--model", "sonnet",
           "--output-format", "stream-json", "--verbose", "--include-partial-messages",
           "--tools", "Read,WebFetch,WebSearch", "--allowedTools", "Read,WebFetch,WebSearch",
           "--strict-mcp-config", "--disable-slash-commands",
           "--append-system-prompt", sistema]
    cmd += ["--session-id", sessao] if primeira else ["--resume", sessao]

    texto, ultimo_envio, resultado, erro = "", 0.0, None, ""
    inicio = time.time()
    proc = subprocess.Popen(cmd, cwd=str(CTX["estado"]), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    escrever({"t": "inicio"})
    try:
        for linha in proc.stdout:
            try:
                ev = json.loads(linha)
            except ValueError:
                continue
            tipo = ev.get("type")
            if tipo == "stream_event":
                x = ev.get("event") or {}
                if x.get("type") == "message_start":
                    texto = ""
                elif x.get("type") == "content_block_delta" and (x.get("delta") or {}).get("type") == "text_delta":
                    texto += x["delta"].get("text", "")
                    if time.time() - ultimo_envio > 0.07:
                        ultimo_envio = time.time()
                        partes = _partes(texto)
                        if "folha" in partes:
                            partes["folha"] = sanear_html(partes["folha"])[0]
                        if partes.get("estilo_fechou") and _ler_estilo(partes["estilo"]):
                            partes["estilo_css"] = css_estilo(normalizar_estilo(e.get("estilo"), _ler_estilo(partes["estilo"])))
                        escrever({"t": "parcial", **partes})
            elif tipo == "assistant":
                for bloco in (ev.get("message") or {}).get("content") or []:
                    if bloco.get("type") == "tool_use":
                        escrever({"t": "lendo"})
            elif tipo == "result":
                resultado = ev
                if ev.get("is_error"):
                    erro = str(ev.get("result") or "erro do Ultron")[:300]
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    if resultado and not erro and (resultado.get("result") or "").strip():
        texto = resultado["result"] if "<" in resultado["result"] else texto
    if not texto.strip():
        erro = erro or (proc.stderr.read() or "").strip()[-300:] or "O Ultron não respondeu."
        CTX["log"]({"evento": "curriculo_falhou", "modo": modo, "detalhe": erro})
        if not primeira and "session" in erro.lower():
            with TRAVA:
                est = ler_estado()
                est.setdefault(modo, {}).pop("sessao", None)
                salvar_estado(est)
        raise ValueError("O Ultron não conseguiu responder agora: " + erro[:160])

    p = _partes(texto)
    with TRAVA:
        est = ler_estado()
        e2 = est.setdefault(modo, {})
        e2["sessao"] = sessao
        if curriculo_atual is not None and e.get("curriculo"):
            e2["curriculo"] = e["curriculo"]
            if html_atual:
                e2["html"], e2["html_md"] = sanear_html(html_atual)[0], e2["curriculo"]
        if p.get("curriculo") and (modo == "adaptar" or not e2.get("curriculo")):
            e2["curriculo"] = p["curriculo"]
        if modo == "analisar" and p.get("folha") and not e2.get("curriculo"):
            limpo, arvore = sanear_html(p["folha"])
            if _texto_no(arvore).strip():
                e2["curriculo"] = md_de_arvore(arvore)
                e2["html"], e2["html_md"] = limpo, e2["curriculo"]
        if p.get("estilo") and _ler_estilo(p["estilo"]):
            e2["estilo"] = normalizar_estilo(e2.get("estilo"), _ler_estilo(p["estilo"]))
        if p.get("analise"):
            try:
                bruto = p["analise"]
                e2["analise"] = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
            except ValueError:
                pass
        conversa = e2.setdefault("conversa", [])
        if mensagem.strip():
            conversa.append({"quem": "eu", "texto": mensagem.strip()[:4000]})
        resposta = p.get("mensagem") or ("" if p.get("curriculo") or p.get("analise") or p.get("estilo") else texto.strip())
        if resposta:
            conversa.append({"quem": "claude", "texto": resposta[:6000]})
        salvar_estado(est)
    CTX["log"]({"evento": "curriculo", "modo": modo, "segundos": round(time.time() - inicio, 1)})
    escrever({"t": "fim", "estado": estado_publico()})



def _blocos(md):
    """Markdown simples -> [(tipo, texto, recuo)]: h1, contato, h2, h3, li, p, hr, espaco.
    Recuo: cada 2 espaços no começo da linha = 1 nível (até 3). "&nbsp;" sozinho = linha em branco."""
    blocos, anterior = [], None
    for linha in md.splitlines():
        l = linha.strip()
        recuo = min(3, (len(linha) - len(linha.lstrip(" "))) // 2)
        if not l:
            anterior = None if anterior != "h1" else "h1"
            continue
        if l == "&nbsp;":
            blocos.append(("espaco", "", 0))
            anterior = "espaco"
            continue
        if re.fullmatch(r"(-\s*){3,}|(\*\s*){3,}|(_\s*){3,}", l):
            b = ("hr", "")
        elif l.startswith("### "):
            b = ("h3", l[4:])
        elif l.startswith("## "):
            b = ("h2", l[3:])
        elif l.startswith("# "):
            b = ("h1", l[2:])
        elif re.match(r"[-*•]\s+", l):
            b = ("li", re.sub(r"^[-*•]\s+", "", l))
        elif anterior == "h1":
            b = ("contato", l)
        else:
            b = ("p", l)
        blocos.append(b + (recuo if b[0] in ("p", "li", "h3") else 0,))
        anterior = b[0]
    return blocos


def _runs(texto):
    """'a **b** *c*' -> [(texto, negrito, italico)]"""
    saida = []
    for parte in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**") and len(parte) > 4:
            saida.append((parte[2:-2], True, False))
        elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
            saida.append((parte[1:-1], False, True))
        else:
            saida.append((parte, False, False))
    return saida


def gerar_docx(md, estilo=None, arvore=None):
    est = normalizar_estilo(estilo)
    meio = round(est["tamanho"] * 2)
    cor = est["cor"].lstrip("#").upper()
    mult, _, linha_word = ESPACOS[est["espacamento"]]
    jc = "left" if est["nome_alinhado"] == "esquerda" else "center"
    jc_texto = '<w:jc w:val="both"/>' if est["texto_alinhado"] == "justificado" else ""
    borda = (f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{cor}"/></w:pBdr>' if est["linhas"] else "")

    def esp(antes, depois):
        return f'<w:spacing w:before="{round(antes * mult)}" w:after="{round(depois * mult)}"/>'

    def esc(t):
        return html.escape(t, quote=False)

    def run(t, b=False, i=False, tam=None, cor=None):
        props = ("<w:b/>" if b else "") + ("<w:i/>" if i else "") + (f'<w:color w:val="{cor}"/>' if cor else "") + \
                (f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>' if tam else "")
        return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{esc(t)}</w:t></w:r>'

    def par(conteudo, ppr=""):
        return f"<w:p><w:pPr>{ppr}</w:pPr>{conteudo}</w:p>"

    corpo = _corpo_docx_html(arvore, est) if arvore is not None else []
    for tipo, t, recuo in ([] if arvore is not None else _blocos(md)):
        ind = recuo * 425
        if tipo == "espaco":
            corpo.append(par("", esp(0, 0)))
        elif tipo == "h1":
            corpo.append(par(run(t, b=True, tam=round(meio * 2)), esp(0, 40) + f'<w:jc w:val="{jc}"/>'))
        elif tipo == "contato":
            corpo.append(par(run(t, tam=round(meio * .9), cor="555555"), esp(0, 160) + f'<w:jc w:val="{jc}"/>'))
        elif tipo == "h2":
            corpo.append(par(run(t.upper() if est["maiusculas"] else t, b=True, tam=round(meio * 1.1), cor=cor),
                             borda + esp(220, 80)))
        elif tipo == "hr":
            corpo.append(par("", f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{cor}"/></w:pBdr>'
                             + esp(40, 100) + '<w:rPr><w:sz w:val="4"/></w:rPr>'))
        elif tipo == "h3":
            corpo.append(par("".join(run(x, True, i) for x, _, i in _runs(t)),
                             esp(100, 30) + (f'<w:ind w:left="{ind}"/>' if ind else "")))
        elif tipo == "li":
            corpo.append(par(run("•\t") + "".join(run(x, b, i) for x, b, i in _runs(t)),
                             f'<w:tabs><w:tab w:val="left" w:pos="{284 + ind}"/></w:tabs>' + esp(0, 30)
                             + f'<w:ind w:left="{284 + ind}" w:hanging="284"/>' + jc_texto))
        else:
            corpo.append(par("".join(run(x, b, i) for x, b, i in _runs(t)),
                             esp(0, 80) + (f'<w:ind w:left="{ind}"/>' if ind else "") + jc_texto))
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    documento = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {w}><w:body>{"".join(corpo)}'
                 '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="964" w:right="1021" w:bottom="964" '
                 'w:left="1021" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:body></w:document>')
    estilos = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {w}><w:docDefaults><w:rPrDefault>'
               f'<w:rPr><w:rFonts w:ascii="{FONTES[est["fonte"]][1]}" w:hAnsi="{FONTES[est["fonte"]][1]}" '
               f'w:cs="{FONTES[est["fonte"]][1]}"/><w:sz w:val="{meio}"/>'
               f'<w:szCs w:val="{meio}"/><w:lang w:val="pt-BR"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
               f'<w:spacing w:after="0" w:line="{linha_word}" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>')
    tipos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/'
             'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
             'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/'
             'document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.styles+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.'
            'org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.'
                'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
                'openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    buf = _bytes_io(b"")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", documento)
        z.writestr("word/styles.xml", estilos)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
    return buf.getvalue()


def html_folha(md):
    """Mesmo HTML que a tela desenha (usado no PDF)."""
    def inline(t):
        return "".join(f"<strong>{html.escape(x)}</strong>" if b else f"<em>{html.escape(x)}</em>" if i else html.escape(x)
                       for x, b, i in _runs(t))
    partes, lista = [], False
    for tipo, t, recuo in _blocos(md):
        if tipo == "li" and not lista:
            partes.append("<ul>")
            lista = True
        elif tipo != "li" and lista:
            partes.append("</ul>")
            lista = False
        if tipo == "hr":
            partes.append("<hr>")
            continue
        if tipo == "espaco":
            partes.append('<p class="espaco">&nbsp;</p>')
            continue
        tag = {"h1": "h1", "h2": "h2", "h3": "h3", "li": "li", "contato": 'p class="contato"'}.get(tipo, "p")
        if recuo:
            tag += f' class="r{recuo}"' if " " not in tag else ""
        partes.append(f"<{tag}>{inline(t)}</{tag.split()[0]}>")
    if lista:
        partes.append("</ul>")
    return "".join(partes)



_TAGS = {"p", "div", "h1", "h2", "h3", "ul", "ol", "li", "br", "b", "strong", "i", "em", "u", "hr", "span"}
_CLASSES = {"contato", "espaco", "r1", "r2", "r3", "marcador"}
_BLOCOS = {"p", "div", "h1", "h2", "h3", "ul", "ol", "li", "hr"}


class _Leitor(HTMLParser):
    """Lê o HTML da folha guardando só o que importa (tags de texto e as classes da folha). Estilos colados somem."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = {"tag": "raiz", "cls": [], "filhos": []}
        self.pilha = [self.raiz]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style"):
            tag = "lixo"
        elif tag not in _TAGS:
            tag = "span"
        cls = [c for c in (dict(attrs).get("class") or "").split() if c in _CLASSES]
        no = {"tag": tag, "cls": cls, "filhos": []}
        self.pilha[-1]["filhos"].append(no)
        if tag not in ("br", "hr"):
            self.pilha.append(no)

    def handle_endtag(self, tag):
        tag = tag.lower()
        tag = tag if tag in _TAGS or tag in ("script", "style") else "span"
        tag = "lixo" if tag in ("script", "style") else tag
        for i in range(len(self.pilha) - 1, 0, -1):
            if self.pilha[i]["tag"] == tag:
                del self.pilha[i:]
                break

    def handle_data(self, dados):
        if self.pilha[-1]["tag"] != "lixo":
            self.pilha[-1]["filhos"].append(dados)


def _texto_no(no):
    return no if isinstance(no, str) else "".join(_texto_no(f) for f in no["filhos"])


def _html_no(no):
    if isinstance(no, str):
        return html.escape(no, quote=False)
    if no["tag"] == "lixo":
        return ""
    dentro = "".join(_html_no(f) for f in no["filhos"])
    if no["tag"] == "raiz" or (no["tag"] == "span" and not no["cls"]):
        return dentro
    cls = f' class="{" ".join(no["cls"])}"' if no["cls"] else ""
    if no["tag"] in ("br", "hr"):
        return f"<{no['tag']}{cls}>"
    return f"<{no['tag']}{cls}>{dentro}</{no['tag']}>"


def sanear_html(bruto):
    """HTML da tela -> (HTML limpo, árvore). Fica só texto, negrito, itálico, sublinhado, listas, títulos, linhas e recuos."""
    leitor = _Leitor()
    leitor.feed(str(bruto or "")[:300000])
    leitor.close()
    return _html_no(leitor.raiz), leitor.raiz


def _corpo_docx_html(arvore, est):
    """Árvore da folha -> parágrafos do Word, com as mesmas medidas da tela (curriculo-folha.css)."""
    meio = round(est["tamanho"] * 2)
    cor = est["cor"].lstrip("#").upper()
    mult = ESPACOS[est["espacamento"]][0]
    jc_nome = "left" if est["nome_alinhado"] == "esquerda" else "center"
    jc_texto = "both" if est["texto_alinhado"] == "justificado" else ""
    linha = f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{cor}"/></w:pBdr>'
    corpo = []

    def twip(px):
        return round(px * 15 * mult)

    def ppr(antes=0, depois=0, ind=0, jc="", borda="", pendurado=0, tab=0):
        x = borda + (f'<w:tabs><w:tab w:val="left" w:pos="{tab}"/></w:tabs>' if tab else "")
        x += f'<w:spacing w:before="{twip(antes)}" w:after="{twip(depois)}"/>'
        if ind or pendurado:
            x += f'<w:ind w:left="{ind}"' + (f' w:hanging="{pendurado}"' if pendurado else "") + "/>"
        return x + (f'<w:jc w:val="{jc}"/>' if jc else "")

    def pedacos(no, b=False, i=False, u=False, fora=()):
        """Texto inline -> [(texto, b, i, u)] e "BR" pras quebras de linha."""
        if isinstance(no, str):
            return [(re.sub(r"\s+", " ", no), b, i, u)]
        t = no["tag"]
        if t == "br":
            return ["BR"]
        if t in fora or t == "lixo":
            return []
        b, i, u = b or t in ("b", "strong"), i or t in ("i", "em"), u or t == "u"
        saida = []
        for f in no["filhos"]:
            saida += pedacos(f, b, i, u, fora)
        return saida

    def runs(lista, negrito=False, tam=None, cor_run=None, maiusc=False):
        lista = [x for x in lista if x == "BR" or x[0]]
        xml, inicio = [], True
        for k, x in enumerate(lista):
            if x == "BR":
                if k != len(lista) - 1:
                    xml.append("<w:r><w:br/></w:r>")
                inicio = True
                continue
            texto, b, i, u = x
            if inicio:
                texto = texto.lstrip()
            if k == len(lista) - 1 or lista[k + 1] == "BR":
                texto = texto.rstrip()
            if not texto:
                continue
            inicio = False
            if maiusc:
                texto = texto.upper()
            props = ("<w:b/>" if b or negrito else "") + ("<w:i/>" if i else "") + \
                    (f'<w:color w:val="{cor_run}"/>' if cor_run else "") + \
                    (f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>' if tam else "") + ('<w:u w:val="single"/>' if u else "")
            xml.append(f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{html.escape(texto, quote=False)}</w:t></w:r>')
        return "".join(xml)

    def par(conteudo, propriedades):
        corpo.append(f"<w:p><w:pPr>{propriedades}</w:pPr>{conteudo}</w:p>")

    def recuo_de(no):
        return next((int(c[1]) for c in no["cls"] if c in ("r1", "r2", "r3")), 0)

    def paragrafo(no, lista_inline, extra_recuo=0):
        cls = no["cls"] if isinstance(no, dict) else []
        ind = (recuo_de(no) if isinstance(no, dict) else 0) * 425 + extra_recuo
        vazio = not "".join(x[0] for x in lista_inline if x != "BR").strip()
        if "espaco" in cls or vazio:
            par("", ppr())
        elif "contato" in cls:
            par(runs(lista_inline, tam=round(meio * .9), cor_run="555555"), ppr(0, 12, ind, jc_nome))
        else:
            depois = 5 if isinstance(no, dict) and no["tag"] == "p" else 0
            par(runs(lista_inline), ppr(0, depois, ind, jc_texto))

    def lista_word(no, nivel):
        numerada = no["tag"] == "ol"
        k = 0
        for li in no["filhos"]:
            if isinstance(li, str) or li["tag"] != "li":
                continue
            k += 1
            ind = 284 + (nivel + recuo_de(li)) * 425
            marca = f"{k}.\t" if numerada else "•\t"
            texto = pedacos(li, fora=("ul", "ol"))
            par(f'<w:r><w:t xml:space="preserve">{marca}</w:t></w:r>' + runs(texto),
                ppr(0, 2, ind, jc_texto, pendurado=284, tab=ind))
            for sub in li["filhos"]:
                if isinstance(sub, dict) and sub["tag"] in ("ul", "ol"):
                    lista_word(sub, nivel + 1)

    def blocos(no, extra_recuo=0):
        solto = []

        def soltar():
            if solto and "".join(x[0] for x in solto if x != "BR").strip():
                par(runs(solto), ppr(0, 5, extra_recuo, jc_texto))
            solto.clear()

        for f in no["filhos"]:
            t = None if isinstance(f, str) else f["tag"]
            if t is None or t not in _BLOCOS:
                solto.extend(pedacos(f))
                continue
            soltar()
            if t == "hr":
                par("", linha + ppr(8, 8) + '<w:rPr><w:sz w:val="4"/></w:rPr>')
            elif t == "h1":
                par(runs(pedacos(f), negrito=True, tam=round(meio * 2)), ppr(0, 2, 0, jc_nome))
            elif t == "h2":
                par(runs(pedacos(f), negrito=True, tam=round(meio * 1.1), cor_run=cor, maiusc=est["maiusculas"]),
                    (linha if est["linhas"] else "") + ppr(14, 6))
            elif t == "h3":
                par(runs(pedacos(f), negrito=True), ppr(8, 2, recuo_de(f) * 425))
            elif t in ("ul", "ol"):
                lista_word(f, 0)
            elif t == "li":
                lista_word({"tag": "ul", "cls": [], "filhos": [f]}, 0)
            elif any(isinstance(x, dict) and x["tag"] in _BLOCOS for x in f["filhos"]):
                blocos(f, extra_recuo + recuo_de(f) * 425)
            else:
                paragrafo(f, pedacos(f), extra_recuo)
        soltar()

    blocos(arvore)
    return corpo


def _navegador():
    candidatos = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)") + r"\Microsoft\Edge\Application\msedge.exe",
                  os.environ.get("ProgramFiles", r"C:\Program Files") + r"\Microsoft\Edge\Application\msedge.exe",
                  os.environ.get("ProgramFiles", r"C:\Program Files") + r"\Google\Chrome\Application\chrome.exe",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return shutil.which("msedge") or shutil.which("google-chrome") or shutil.which("chromium")


def gerar_pdf(md, estilo=None, html_limpo=None):
    nav = _navegador()
    if not nav:
        raise ValueError("Não achei o Edge nem o Chrome pra gerar o PDF.")
    css = (CTX["web"] / "curriculo-folha.css").read_text(encoding="utf-8")
    pagina = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head>'
              f'<body class="impressao"><div class="folha" style="{html.escape(css_estilo(estilo))}">{html_limpo or html_folha(md)}</div></body></html>')
    with tempfile.TemporaryDirectory() as tmp:
        entrada, saida = Path(tmp) / "curriculo.html", Path(tmp) / "curriculo.pdf"
        entrada.write_text(pagina, encoding="utf-8")
        subprocess.run([nav, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                        f"--user-data-dir={Path(tmp) / 'perfil'}", f"--print-to-pdf={saida}", entrada.as_uri()],
                       capture_output=True, timeout=60)
        if not saida.exists():
            raise ValueError("O navegador não conseguiu gerar o PDF.")
        return saida.read_bytes()


def exportar(formato, md, estilo=None, html_tela=None):
    """html_tela: a folha exatamente como está na tela. Com ele, o Word e o PDF saem iguais ao que ele vê."""
    if not md.strip() and not html_tela:
        raise ValueError("A folha está vazia.")
    limpo, arvore = sanear_html(html_tela) if html_tela else ("", None)
    if arvore is not None and not _texto_no(arvore).strip():
        limpo, arvore = "", None
    if formato == "docx":
        dados = gerar_docx(md, estilo, arvore)
    else:
        dados = gerar_pdf(md, estilo, limpo or None)
    nome = re.sub(r"[^\w-]+", "-", next((t for tp, t, _ in _blocos(md) if tp == "h1"), "curriculo")).strip("-")[:40]
    nome = f"Curriculo-{nome or 'novo'}.{formato}"
    try:
        destino = CTX["pasta"] / "curriculo"
        destino.mkdir(exist_ok=True)
        (destino / f"{time.strftime('%Y-%m-%d')}-{nome}").write_bytes(dados)
    except OSError:
        pass
    return nome, dados
