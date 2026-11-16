"""Controle do PC (Windows): uso, volume, música, janelas, programas e coisas do sistema.

Porta de entrada única: `executar(acao, alvo)` (a barra do topo, os comandos de voz e o atalhos/pc.py passam por
ela) e `estado()` (o que o painel da barra mostra). Cada assunto fica no seu arquivo, sem nada pra instalar.
"""
from .acoes import ACOES, estado, executar  # noqa: F401
