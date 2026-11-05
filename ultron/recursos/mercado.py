"""Painel do mercado: roda o atalhos/mercado.py e transforma a linha de texto dele em itens pro painel."""
import re
import subprocess
import sys

from ..nucleo.config import ATALHOS, RAIZ
from ..nucleo.log import log_erro
from .paineis import PAINEIS, avisar_paineis

# "Dólar R$ 5,40 (+0,3%)" ou "Ibovespa 128.000 pontos (-1,2%)"
RE_ITEM = re.compile(r"(.+?) (R\$ [\d.,]+|[\d.,]+ pontos) \(([-+][\d,]+%)")


def atualizar_mercado():
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(ATALHOS / "mercado.py")], cwd=str(RAIZ),
                           capture_output=True, text=True, encoding="utf-8", timeout=20)
        itens = []
        for parte in r.stdout.strip().split(" | "):
            m = RE_ITEM.match(parte)
            if m:
                itens.append({"nome": m.group(1), "valor": m.group(2).replace(" pontos", ""), "variacao": m.group(3)})
        if itens:
            PAINEIS["mercado"] = itens
            avisar_paineis()
    except Exception as erro:
        log_erro("paineis_falhou", erro, onde="mercado")
