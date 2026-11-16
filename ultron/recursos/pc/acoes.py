"""As ações do controle do PC, cada uma com a frase curta do que fez (é ela que o Ultron fala)."""
import sys

from . import janelas, midia, programas, sistema, uso, volume


def estado():
    """O que o painel da barra mostra: uso do PC, volume e o que está tocando."""
    return {"uso": uso.uso(), "volume": volume.ler(), "tocando": midia.tocando()}


def executar(acao, alvo=""):
    """Faz a ação e devolve a frase do que fez. ValueError: ação desconhecida, alvo errado ou fora do Windows."""
    if sys.platform != "win32":
        raise ValueError("Controlar o PC só funciona no Windows.")
    if acao not in ACOES:
        raise ValueError(f"Não conheço a ação '{acao}'. As que existem: {', '.join(ACOES)}.")
    return ACOES[acao](str(alvo or "").strip())


def _numero(alvo, nome):
    try:
        return int(float(alvo.replace("%", "").replace(",", ".")))
    except ValueError:
        raise ValueError(f"{nome} precisa de um número de 0 a 100.") from None


def _volume(alvo):
    return f"Volume em {volume.mudar(_numero(alvo, 'O volume'))['nivel']}."


def _mais_volume(alvo):
    return f"Volume em {volume.somar(_numero(alvo or '10', 'O passo'))['nivel']}."


def _menos_volume(alvo):
    return f"Volume em {volume.somar(-_numero(alvo or '10', 'O passo'))['nivel']}."


def _mudo(_):
    volume.silenciar(True)
    return "Sem som."


def _som(_):
    volume.silenciar(False)
    return "Som de volta."


def _tocar_pausar(_):
    midia.apertar("tocar_pausar")
    return "Feito."


def _proxima(_):
    midia.apertar("proxima")
    return "Próxima."


def _anterior(_):
    midia.apertar("anterior")
    return "Voltei uma."


def _tocando(_):
    t = midia.tocando()
    if not t.get("titulo"):
        return "Nada tocando agora."
    artista = f", de {t['artista']}" if t.get("artista") else ""
    return f"{'Tocando' if t.get('tocando') else 'Pausado'}: {t['titulo']}{artista}, no {t.get('app') or 'PC'}."


def _abrir(alvo):
    programas.abrir(alvo)
    return f"Abrindo {alvo}."


def _fechar(alvo):
    programas.fechar(alvo)
    return f"Fechei {alvo}."


def _focar(alvo):
    janelas.focar(alvo)
    return f"{alvo.capitalize()} na frente."


def _minimizar(alvo):
    janelas.minimizar(alvo)
    return f"Minimizei {alvo}."


def _maximizar(alvo):
    janelas.maximizar(alvo)
    return f"{alvo.capitalize()} em tela cheia."


def _area_de_trabalho(_):
    janelas.area_de_trabalho()
    return "Área de trabalho."


def _janelas(_):
    return "\n".join(f"{j.programa}: {j.titulo}" for j in janelas.listar()) or "Nenhuma janela aberta."


def _bloquear(_):
    sistema.bloquear()
    return "Bloqueado."


def _brilho(alvo):
    return f"Brilho em {sistema.brilho(_numero(alvo, 'O brilho') if alvo else None)}."


def _mais_brilho(alvo):
    return f"Brilho em {sistema.brilho(sistema.brilho() + _numero(alvo or '20', 'O passo'))}."


def _menos_brilho(alvo):
    return f"Brilho em {sistema.brilho(sistema.brilho() - _numero(alvo or '20', 'O passo'))}."


def _configuracoes(alvo):
    pagina = sistema.configuracoes(alvo)
    return f"Configurações de {alvo} abertas." if pagina else "Configurações abertas."


def _recortar(_):
    sistema.recortar_tela()
    return "Escolha a área."


def _uso(_):
    u = uso.uso()
    partes = [f"processador em {u['processador']}%", f"memória em {u['memoria']['pct']}%",
              f"disco em {u['disco']['pct']}%"]
    if u["placa_de_video"]:
        video = u["placa_de_video"]
        partes.append(f"placa de vídeo em {video['pct']}%, a {video['temperatura']} graus")
    if u["bateria"]:
        partes.append(f"bateria em {u['bateria']['pct']}%" + (", carregando" if u["bateria"]["carregando"] else ""))
    return "Agora: " + ", ".join(partes) + "."


ACOES = {
    "volume": _volume, "mais_volume": _mais_volume, "menos_volume": _menos_volume, "mudo": _mudo, "som": _som,
    "tocar_pausar": _tocar_pausar, "proxima": _proxima, "anterior": _anterior, "tocando": _tocando,
    "abrir": _abrir, "fechar": _fechar, "focar": _focar, "minimizar": _minimizar, "maximizar": _maximizar,
    "area_de_trabalho": _area_de_trabalho, "janelas": _janelas, "bloquear": _bloquear, "brilho": _brilho,
    "mais_brilho": _mais_brilho, "menos_brilho": _menos_brilho,
    "configuracoes": _configuracoes, "recortar": _recortar, "uso": _uso,
}
