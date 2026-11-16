"""Painel de música: playlists, pesquisa no YouTube, adicionar link, guardar e tirar músicas."""
from ...nucleo.log import log_erro
from ...recursos import musica
from ..servidor import rota


def _pelo_youtube(acao, faz):
    """Roda `faz()`. Link inválido (ValueError) vira 400 no roteador; outro erro = YouTube fora do ar."""
    try:
        return faz()
    except ValueError:
        raise
    except Exception as erro:
        log_erro("musica_falhou", erro, acao=acao)
        return 502, {"erro": "Não consegui falar com o YouTube agora."}


@rota("GET", "/api/musica")
def playlists(pedido):
    return musica.playlists(forcar=pedido.tem_param("atualizar"))


@rota("GET", "/api/musica/buscar")
def buscar(pedido):
    q = pedido.param("q").strip()[:120]
    try:
        return {"itens": musica.buscar(q) if q else []}
    except Exception as erro:
        log_erro("musica_busca_falhou", erro)
        return 502, {"erro": "Não consegui pesquisar agora."}


@rota("POST", "/api/musica/adicionar")
def adicionar(pedido):
    link = str(pedido.json().get("link", ""))
    return _pelo_youtube("adicionar", lambda: musica.adicionar_link(link))


@rota("POST", "/api/musica/avulsa")
def guardar_avulsa(pedido):
    item = pedido.json().get("item") or {}
    return _pelo_youtube("avulsa", lambda: {"item": musica.avulsa(item)})


@rota("POST", "/api/musica/tirar-avulsa")
def tirar_avulsa(pedido):
    musica.tirar_avulsa(str(pedido.json().get("id", "")))
    return {"ok": True}


@rota("POST", "/api/musica/tirar-playlist")
def tirar_playlist(pedido):
    musica.tirar_playlist(str(pedido.json().get("id", "")))
    return {"ok": True}
