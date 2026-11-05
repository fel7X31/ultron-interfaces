"""Ler e gravar JSON em disco sem repetir try/except em todo lugar."""
import json
from pathlib import Path


def ler_json(caminho, padrao=None):
    """Conteúdo do arquivo JSON, ou `padrao` se ele não existe ou está quebrado."""
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return padrao


def salvar_json(caminho, dados, indent=None):
    """Grava o JSON (cria a pasta se precisar). Grava num .tmp e troca, pra nunca ficar arquivo pela metade."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_name(caminho.name + ".tmp")
    temp.write_text(json.dumps(dados, ensure_ascii=False, indent=indent), encoding="utf-8")
    temp.replace(caminho)
