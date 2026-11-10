"""Uma arquivo de rotas por assunto. Importar este pacote registra todas (veja servidor.criar_servidor).

Rota nova: crie (ou abra) o arquivo do assunto, use @rota(...) e, se o arquivo for novo, importe-o aqui.
A rota só lê o pedido e chama o recurso: a regra fica em ultron/recursos/.
"""
from . import curriculo  # noqa: F401
from . import conversa, paineis, provas, sistema  # noqa: F401
from . import musica  # noqa: F401
