"""Músicas do painel de música: lê as playlists do YouTube do dono (título, artista, duração) e guarda em cache.

Sem biblioteca externa: lê o ytInitialData da página da playlist. O áudio toca no navegador pelo player do YouTube.
"""
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
_trava = threading.Lock()
_cache_arquivo = ESTADO / "musica.json"          # as playlists baixadas (vale por 12 h)


def _textos(n, out):
    if isinstance(n, dict):
        if isinstance(n.get("content"), str):
            out.append(n["content"])
        for v in n.values():
            _textos(v, out)
    elif isinstance(n, list):
        for x in n:
            _textos(x, out)
    return out


def _segundos(txt):
    s = 0
    for parte in (txt or "").split(":"):
        s = s * 60 + int(parte) if parte.isdigit() else s
    return s


def _ler(lid):
    url = f"https://www.youtube.com/playlist?list={lid}&hl=pt-BR"
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8")
    dados = json.loads(re.search(r"var ytInitialData = (\{.*?\});</script>", html).group(1))
    titulo = dados.get("metadata", {}).get("playlistMetadataRenderer", {}).get("title", "") or "Playlist"
    itens, vistos = [], set()

    def andar(n):
        if isinstance(n, dict):
            if "lockupViewModel" in n:
                v = n["lockupViewModel"]
                if v.get("contentType", "") not in ("", "LOCKUP_CONTENT_TYPE_VIDEO"):
                    return
                meta = v.get("metadata", {}).get("lockupMetadataViewModel", {})
                linhas = _textos(meta.get("metadata", {}), [])
                dur = re.findall(r'"text": "(\d+:\d+(?::\d+)?)"', json.dumps(v.get("contentImage", {})))
                vid = v.get("contentId")
                if vid and vid not in vistos:
                    vistos.add(vid)
                    artista = (linhas[0] if linhas else "").replace(" - Topic", "").strip()
                    itens.append({"id": vid, "titulo": meta.get("title", {}).get("content", ""), "artista": artista,
                                  "dur": _segundos(dur[0]) if dur else 0})
                return
            for x in n.values():
                andar(x)
        elif isinstance(n, list):
            for x in n:
                andar(x)
    andar(dados)
    return {"id": lid, "titulo": titulo, "itens": itens}


def _lista_ids():
    """As playlists que aparecem: as duas de sempre + as que você adicionou, menos as que você tirou."""
    m = _minhas()
    ids = [x for x in PLAYLISTS if x not in m["tiradas"]] + [x for x in m["extras"] if x not in PLAYLISTS]
    return ids


def _minhas():
    d = ler_json(ESTADO / "musica-minhas.json", {}) or {}
    return {"extras": d.get("extras", []), "tiradas": d.get("tiradas", []), "avulsas": d.get("avulsas", [])}


def _salvar_minhas(m):
    salvar_json(ESTADO / "musica-minhas.json", m, indent=1)


def _com_avulsas(d):
    d = dict(d)
    av = _minhas()["avulsas"]
    ids = _lista_ids()
    d["playlists"] = ([{"id": "avulsas", "titulo": "Avulsas", "itens": av, "avulsa": True}] if av else []) + \
        sorted((p for p in d.get("playlists", []) if p["id"] in ids), key=lambda p: ids.index(p["id"]))
    return d


def playlists(forcar=False):
    with _trava:
        cache = None
        if _cache_arquivo and _cache_arquivo.exists():
            try:
                cache = json.loads(_cache_arquivo.read_text(encoding="utf-8"))
            except Exception:
                cache = None
        ids = _lista_ids()
        tem_todas = cache and all(any(p["id"] == lid for p in cache.get("playlists", [])) for lid in ids)
        if cache and tem_todas and not forcar and time.time() - cache.get("quando", 0) < VALIDADE:
            return _com_avulsas(cache)
        listas, erro = [], ""
        for lid in ids:
            velha = next((p for p in (cache or {}).get("playlists", []) if p["id"] == lid), None)
            if velha and not forcar and tem_todas is False and time.time() - (cache or {}).get("quando", 0) < VALIDADE:
                listas.append(velha)  # só faltava a nova: não baixa as outras de novo
                continue
            try:
                listas.append(_ler(lid))
            except Exception as e:  # sem internet ou o YouTube mudou a página: usa o que já tinha
                erro = repr(e)[:200]
                if velha:
                    listas.append(velha)
        novo = {"quando": time.time(), "playlists": listas}
        if listas and not erro and _cache_arquivo:
            _cache_arquivo.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
        if erro:
            novo["erro"] = "Não consegui atualizar as playlists agora."
        return _com_avulsas(novo)


def buscar(q, limite=8):
    """Pesquisa no YouTube (só vídeos). Devolve [{id, titulo, artista, dur}]."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=EgIQAQ%3D%3D&hl=pt-BR"
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8")
    dados = json.loads(re.search(r"var ytInitialData = (\{.*?\});</script>", html).group(1))
    out = []

    def andar(n):
        if len(out) >= limite:
            return
        if isinstance(n, dict):
            if "videoRenderer" in n:
                v = n["videoRenderer"]
                if v.get("videoId") and v.get("lengthText"):  # sem duração = ao vivo / estreia
                    out.append({"id": v["videoId"],
                                "titulo": "".join(r.get("text", "") for r in v.get("title", {}).get("runs", [])),
                                "artista": "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])).replace(" - Topic", ""),
                                "dur": _segundos(v.get("lengthText", {}).get("simpleText", ""))})
                return
            for x in n.values():
                andar(x)
        elif isinstance(n, list):
            for x in n:
                andar(x)
    andar(dados)
    return out


def _info_video(vid):
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + vid)
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10).read().decode("utf-8"))
        return {"id": vid, "titulo": d.get("title", vid), "artista": d.get("author_name", "").replace(" - Topic", ""), "dur": 0}
    except Exception:
        return {"id": vid, "titulo": vid, "artista": "", "dur": 0}


def avulsa(item):
    """Põe uma música na lista Avulsas (a mais recente primeiro, sem repetir)."""
    with _trava:
        m = _minhas()
        item = {k: item.get(k) for k in ("id", "titulo", "artista", "dur")}
        if not re.fullmatch(r"[\w-]{11}", str(item["id"] or "")):
            raise ValueError("id inválido")
        m["avulsas"] = [item] + [x for x in m["avulsas"] if x["id"] != item["id"]]
        m["avulsas"] = m["avulsas"][:200]
        _salvar_minhas(m)
        return item


def tirar_avulsa(vid):
    with _trava:
        m = _minhas()
        m["avulsas"] = [x for x in m["avulsas"] if x["id"] != vid]
        _salvar_minhas(m)


def adicionar_link(link):
    """Link de playlist vira uma aba nova; link de música entra nas Avulsas. Devolve {"tipo", ...}."""
    link = (link or "").strip()
    lista = re.search(r"[?&]list=([\w-]{10,})", link) or re.fullmatch(r"(PL[\w-]{10,})", link)
    video = re.search(r"(?:v=|youtu\.be/|embed/|live/|shorts/)([\w-]{11})", link) or re.fullmatch(r"([\w-]{11})", link)
    if lista and not lista.group(1).startswith(("RD", "UU", "LL", "WL")):  # RD = mix automático do YouTube: trata como música
        lid = lista.group(1)
        pl = _ler(lid)
        if not pl["itens"]:
            raise ValueError("Essa playlist está vazia ou é privada.")
        with _trava:
            m = _minhas()
            if lid not in m["extras"] and lid not in PLAYLISTS:
                m["extras"].append(lid)
            m["tiradas"] = [x for x in m["tiradas"] if x != lid]
            _salvar_minhas(m)
            try:
                cache = json.loads(_cache_arquivo.read_text(encoding="utf-8"))
                cache["playlists"] = [p for p in cache["playlists"] if p["id"] != lid] + [pl]
                _cache_arquivo.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return {"tipo": "playlist", "playlist": pl}
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
