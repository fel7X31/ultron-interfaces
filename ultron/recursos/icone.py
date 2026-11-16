"""O ícone do Ultron (o rosto da barra, do menu e da aba): o robô desenhado ou uma imagem que você mandou.

A imagem fica em .estado/ (fora do git): é sua, não vai pro repositório.
"""
from ..nucleo.config import ESTADO, WEB

TIPOS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAXIMO = 5 * 1024 * 1024
PADRAO = WEB / "icone.svg"


def _personalizado():
    """(arquivo, tipo) da imagem que você mandou, ou None."""
    for tipo, extensao in TIPOS.items():
        arquivo = ESTADO / f"icone{extensao}"
        if arquivo.is_file():
            return arquivo, tipo
    return None


def situacao():
    achou = _personalizado()
    return {"personalizado": bool(achou), "versao": achou[0].stat().st_mtime_ns // 1_000_000 if achou else 0}


def imagem():
    """(bytes, tipo) do ícone que vale agora."""
    achou = _personalizado()
    if achou:
        return achou[0].read_bytes(), achou[1]
    return PADRAO.read_bytes(), "image/svg+xml"


def salvar(dados, tipo):
    tipo = tipo.split(";")[0].strip().lower()
    if tipo not in TIPOS:
        raise ValueError("Mande uma imagem PNG, JPG, WEBP ou GIF.")
    if not dados:
        raise ValueError("A imagem veio vazia.")
    if len(dados) > MAXIMO:
        raise ValueError("Imagem grande demais (até 5 MB).")
    apagar()
    ESTADO.mkdir(exist_ok=True)
    (ESTADO / f"icone{TIPOS[tipo]}").write_bytes(dados)
    return situacao()


def apagar():
    """Volta pro robô desenhado."""
    for extensao in TIPOS.values():
        (ESTADO / f"icone{extensao}").unlink(missing_ok=True)
    return situacao()
