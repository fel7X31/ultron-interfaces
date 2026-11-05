"""Ultron: assistente de voz em cima do Claude Code.

Camadas (de baixo pra cima; cada uma só importa das de baixo):
    nucleo/      infraestrutura sem regra de negócio (config, log, eventos, json, texto, Claude CLI)
    voz/         ouvir (transcrição) e falar (síntese de voz)
    recursos/    cada funcionalidade com a sua regra (tarefas, provas, Google, mercado, música, currículo...)
    assistente/  a conversa: sessão do Claude, comandos de voz e o turno (ouvir → entender → responder)
    http/        servidor web: roteador + rotas de cada recurso
    app.py       liga tudo e sobe o servidor

Veja docs/ARQUITETURA.md.
"""
