"""Log em .estado/log.jsonl: uma linha JSON por acontecimento (turno, erro, painel...)."""
import json
import threading
import time

from .config import ESTADO

LOG_TRAVA = threading.Lock()
ARQUIVO_LOG = ESTADO / "log.jsonl"


def log(registro):
    ESTADO.mkdir(exist_ok=True)
    registro["quando"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_TRAVA, open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def log_erro(evento, erro, **extra):
    """Atalho pro caso mais comum: anota o erro (cortado) com o nome do evento."""
    log({"evento": evento, "detalhe": repr(erro)[:300], **extra})
