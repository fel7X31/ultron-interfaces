"""Músicas do painel de música: lê as playlists do YouTube do dono (título, artista, duração) e guarda em cache.

Sem biblioteca externa: lê o ytInitialData da página da playlist. O áudio toca no navegador pelo player do YouTube.
"""
import itertools
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from ..nucleo.arquivos import ler_json, salvar_json
from ..nucleo.config import ESTADO

PLAYLISTS = ["PLmBA0YDbDAvXGclDUvBUeapD0Pqgo7KhB", "PLmBA0YDbDAvVG_JdOFfQfysWj0oZtMtyp"]
VALIDADE = 12 * 3600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "pt-BR"}
CACHE = ESTADO / "musica.json"
MINHAS = ESTADO / "musica-minhas.json"
_trava = threading.Lock()


def _baixar(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf-8")


def _dados_da_pagina(url):
    """O ytInitialData (os dados que montam a página) de uma página do YouTube."""
    return json.loads(re.search(r"var ytInitialData = (\{.*?\});</script>", _baixar(url)).group(1))


def _procurar(n, chave):
    """Os valores dessa chave em qualquer profundidade do JSON."""
    if isinstance(n, dict):
        if chave in n:
            yield n[chave]
            return
        for v in n.values():
            yield from _procurar(v, chave)
    elif isinstance(n, list):
        for x in n:
            yield from _procurar(x, chave)


def _segundos(txt):
    s = 0
    for parte in (txt or "").split(":"):
        s = s * 60 + int(parte) if parte.isdigit() else s
    return s


def _sem_topic(artista):
    return artista.replace(" - Topic", "").strip()


def _musica_da_playlist(v):
    """Um item da página da playlist -> {id, titulo, artista, dur}, ou None se não for vídeo."""
    if v.get("contentType", "") not in ("", "LOCKUP_CONTENT_TYPE_VIDEO") or not v.get("contentId"):
        return None
    meta = v.get("metadata", {}).get("lockupMetadataViewModel", {})
    linhas = [t for t in _procurar(meta.get("metadata", {}), "content") if isinstance(t, str)]
    dur = re.findall(r'"text": "(\d+:\d+(?::\d+)?)"', json.dumps(v.get("contentImage", {})))
    return {"id": v["contentId"], "titulo": meta.get("title", {}).get("content", ""),
            "artista": _sem_topic(linhas[0] if linhas else ""), "dur": _segundos(dur[0]) if dur else 0}


def _musica_da_busca(v):
    """Um resultado da busca -> {id, titulo, artista, dur}, ou None se for ao vivo (sem duração)."""
    if not v.get("videoId") or not v.get("lengthText"):
        return None
    texto = lambda campo: "".join(r.get("text", "") for r in v.get(campo, {}).get("runs", []))
    return {"id": v["videoId"], "titulo": texto("title"), "artista": _sem_topic(texto("ownerText")),
            "dur": _segundos(v["lengthText"].get("simpleText", ""))}


def _ler(lid):
    """Uma playlist do YouTube: {id, titulo, itens}."""
    dados = _dados_da_pagina(f"https://www.youtube.com/playlist?list={lid}&hl=pt-BR")
    titulo = dados.get("metadata", {}).get("playlistMetadataRenderer", {}).get("title", "") or "Playlist"
    itens, vistos = [], set()
    for musica in map(_musica_da_playlist, _procurar(dados, "lockupViewModel")):
        if musica and musica["id"] not in vistos:
            vistos.add(musica["id"])
            itens.append(musica)
    return {"id": lid, "titulo": titulo, "itens": itens}


def buscar(q, limite=8):
    """Pesquisa no YouTube (só vídeos). Devolve [{id, titulo, artista, dur}]."""
    dados = _dados_da_pagina("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=EgIQAQ%3D%3D&hl=pt-BR")
    achadas = (m for m in map(_musica_da_busca, _procurar(dados, "videoRenderer")) if m)
    return list(itertools.islice(achadas, limite))


def _minhas():
    d = ler_json(MINHAS, {}) or {}
    return {"extras": d.get("extras", []), "tiradas": d.get("tiradas", []), "avulsas": d.get("avulsas", [])}


def _salvar_minhas(m):
    salvar_json(MINHAS, m, indent=1)


def _ler_cache():
    try:
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        return {"quando": c.get("quando", 0), "playlists": c.get("playlists", [])}
    except (FileNotFoundError, ValueError):
        return {"quando": 0, "playlists": []}


def _salvar_cache(cache):
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _lista_ids():
    """As playlists que aparecem: as duas de sempre + as que você adicionou, menos as que você tirou."""
    m = _minhas()
    return [x for x in PLAYLISTS if x not in m["tiradas"]] + [x for x in m["extras"] if x not in PLAYLISTS]


def _com_avulsas(d):
    """A resposta pra tela: a aba Avulsas primeiro, depois as playlists na ordem de _lista_ids()."""
    av = _minhas()["avulsas"]
    ids = _lista_ids()
    abas = sorted((p for p in d["playlists"] if p["id"] in ids), key=lambda p: ids.index(p["id"]))
    return {**d, "playlists": ([{"id": "avulsas", "titulo": "Avulsas", "itens": av, "avulsa": True}] if av else []) + abas}


def playlists(forcar=False):
    """As playlists do painel: as do cache valem 12 h; as que faltam (ou forcar) são baixadas de novo."""
    with _trava:
        cache = _ler_cache()
        valido = not forcar and time.time() - cache["quando"] < VALIDADE
        guardadas = {p["id"]: p for p in cache["playlists"]}
        listas, baixou, falhou = [], False, False
        for lid in _lista_ids():
            if valido and lid in guardadas:
                listas.append(guardadas[lid])
                continue
            try:
                listas.append(_ler(lid))
                baixou = True
            except Exception:
                falhou = True
                if lid in guardadas:
                    listas.append(guardadas[lid])
        novo = {"quando": time.time() if baixou else cache["quando"], "playlists": listas}
        if baixou and not falhou:
            _salvar_cache(novo)
        if falhou:
            novo["erro"] = "Não consegui atualizar as playlists agora."
        return _com_avulsas(novo)


def _info_video(vid):
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + vid)
    try:
        d = json.loads(_baixar(url, timeout=10))
        return {"id": vid, "titulo": d.get("title", vid), "artista": _sem_topic(d.get("author_name", "")), "dur": 0}
    except Exception:
        return {"id": vid, "titulo": vid, "artista": "", "dur": 0}


def avulsa(item):
    """Põe uma música na lista Avulsas (a mais recente primeiro, sem repetir)."""
    with _trava:
        m = _minhas()
        item = {k: item.get(k) for k in ("id", "titulo", "artista", "dur")}
        if not re.fullmatch(r"[\w-]{11}", str(item["id"] or "")):
            raise ValueError("id inválido")
        m["avulsas"] = ([item] + [x for x in m["avulsas"] if x["id"] != item["id"]])[:200]
        _salvar_minhas(m)
        return item


def tirar_avulsa(vid):
    with _trava:
        m = _minhas()
        m["avulsas"] = [x for x in m["avulsas"] if x["id"] != vid]
        _salvar_minhas(m)


def _adicionar_playlist(lid):
    """Baixa a playlist, põe ela nas abas e no cache. Devolve a playlist."""
    pl = _ler(lid)
    if not pl["itens"]:
        raise ValueError("Essa playlist está vazia ou é privada.")
    with _trava:
        m = _minhas()
        if lid not in m["extras"] and lid not in PLAYLISTS:
            m["extras"].append(lid)
        m["tiradas"] = [x for x in m["tiradas"] if x != lid]
        _salvar_minhas(m)
        cache = _ler_cache()
        cache["playlists"] = [p for p in cache["playlists"] if p["id"] != lid] + [pl]
        _salvar_cache(cache)
    return pl


def adicionar_link(link):
    """Link de playlist vira uma aba nova; link de música entra nas Avulsas. Devolve {"tipo", ...}."""
    link = (link or "").strip()
    lista = re.search(r"[?&]list=([\w-]{10,})", link) or re.fullmatch(r"(PL[\w-]{10,})", link)
    video = re.search(r"(?:v=|youtu\.be/|embed/|live/|shorts/)([\w-]{11})", link) or re.fullmatch(r"([\w-]{11})", link)
    if lista and not lista.group(1).startswith(("RD", "UU", "LL", "WL")):
        return {"tipo": "playlist", "playlist": _adicionar_playlist(lista.group(1))}
    if video:
        return {"tipo": "musica", "item": avulsa(_info_video(video.group(1)))}
    raise ValueError("Não reconheci esse link. Cole um link do YouTube (de música ou de playlist).")


def tirar_playlist(lid):
    with _trava:
        m = _minhas()
        if lid in m["extras"]:
            m["extras"].remove(lid)
        elif lid in PLAYLISTS and lid not in m["tiradas"]:
            m["tiradas"].append(lid)
        _salvar_minhas(m)
