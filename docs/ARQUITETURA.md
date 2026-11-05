# Arquitetura do Ultron

O backend é o pacote `ultron/`, em Python puro (só a biblioteca padrão, nada pra instalar com pip).
Ele é dividido em **camadas**. Cada camada só pode importar das camadas **abaixo** dela:

```
        app.py          liga tudo e sobe o servidor
          │
        http/           recebe os pedidos da tela e devolve JSON, áudio, arquivo
          │
     assistente/        a conversa: sessão do Claude, comandos de voz, o turno
          │
      recursos/         cada funcionalidade com a sua regra e os seus dados
          │
   voz/      nucleo/    falar/ouvir · infraestrutura (config, log, eventos, JSON, texto, Claude)
```

Com essa regra, dá pra mexer numa funcionalidade sem medo de quebrar outra. Também dá pra testar um recurso sem
subir o servidor, e qualquer arquivo se lê sozinho: os imports do topo dizem tudo de que ele depende.

## O que tem em cada pasta

```
(pasta do projeto)/
├── server.py                  ponto de entrada (3 linhas). O palmas.py liga por aqui
├── palmas.py                  liga o Ultron com duas palmas (Windows)
├── ultron/
│   ├── app.py                 main(): confere o ambiente, sobe o servidor, aquece o Claude, rotinas dos painéis
│   ├── nucleo/                infraestrutura, sem regra de negócio
│   │   ├── config.py            CFG (configuração viva), caminhos, .env, preferências, persona
│   │   ├── log.py               log() e log_erro() → .estado/log.jsonl
│   │   ├── eventos.py           EVENTOS.emitir(...) avisa a tela ao vivo (Server-Sent Events)
│   │   ├── arquivos.py          ler_json / salvar_json (gravação segura)
│   │   ├── texto.py             normalizar, limpar_para_fala, json_do_texto
│   │   └── claude_cli.py        claude_json(): uma consulta avulsa ao Claude, fora da conversa
│   ├── voz/
│   │   ├── transcricao.py       áudio → texto (whisper local ou ElevenLabs Scribe)
│   │   └── fala.py              texto → voz (ElevenLabs ou Fish Audio), url_fala()
│   ├── recursos/              uma funcionalidade por arquivo
│   │   ├── paineis.py           PAINEIS: o que os painéis da tela mostram
│   │   ├── tarefas.py           tarefas.md, dificuldade/prioridade/prazo e prompt de cada tarefa
│   │   ├── google.py            Gmail e Agenda (pelos conectores do claude.ai)
│   │   ├── mercado.py           dólar, bolsa etc. (roda atalhos/mercado.py)
│   │   ├── provas.py            modo prova
│   │   ├── historico.py         histórico diário das conversas e limpeza semanal
│   │   ├── musica.py            playlists e busca no YouTube
│   │   └── curriculo.py         tela do currículo (analisar e adaptar)
│   ├── assistente/
│   │   ├── sessao.py            o processo do Claude Code que fica aberto (SESSAO)
│   │   ├── comandos.py          comandos de voz que respondem sem o Claude
│   │   ├── confirmacao.py       quando a trava abre ("Confirma?" → "sim")
│   │   ├── prebusca.py          gatilhos.json: dado buscado antes de perguntar
│   │   └── turno.py             processar(): ouvir → comando ou Claude → responder
│   └── http/
│       ├── servidor.py          roteador: @rota("GET", "/api/...")
│       └── rotas/               um arquivo de rotas por assunto
├── web/                       a tela (HTML/CSS/JS, sem build)
├── hooks/                     trava.py (o que precisa de confirmação) e registro.py (log das mudanças do Ultron)
├── atalhos/                   scripts de resposta rápida que o Ultron roda
├── tests/                     python -m unittest discover -s tests
└── docs/
```

## O caminho de uma fala

1. A tela grava enquanto você segura o espaço e manda o áudio para `POST /api/audio` (`http/rotas/conversa.py`).
2. A rota responde 202 na hora e chama `turno.processar()` em outra thread.
3. `voz/transcricao.py` transforma o áudio em texto.
4. `assistente/comandos.py` tenta responder sozinho ("próxima música", "abre o currículo"). Se conseguir, termina aqui,
   em milissegundos.
5. Se não, `confirmacao.py` vê se a trava deve abrir, `prebusca.py` junta dados prontos e `sessao.py` manda a fala
   pro Claude. Se ele for usar ferramenta, sai o aviso "Um instante..." enquanto trabalha.
6. A resposta vai pra tela por `EVENTOS.emitir(...)`, com o link do áudio (`/api/voz/<id>`, gerado por `voz/fala.py`).

## O padrão pra criar uma funcionalidade nova

Exemplo: um painel de clima.

1. **A regra** em `ultron/recursos/clima.py`: funções simples, que recebem e devolvem dados.
   Nada de HTTP aqui. Use o núcleo em vez de reescrever: `ler_json`/`salvar_json`, `log_erro`, `claude_json`,
   `EVENTOS`, `CFG`.

   ```python
   from ..nucleo.log import log_erro
   from .paineis import PAINEIS, avisar_paineis

   def atualizar_clima():
       try:
           PAINEIS["clima"] = ...          # buscar e montar os dados
           avisar_paineis()
       except Exception as erro:
           log_erro("clima_falhou", erro)
   ```

2. **As rotas** em `ultron/http/rotas/clima.py`, e importe o arquivo em `ultron/http/rotas/__init__.py`.
   A rota só lê o pedido e chama o recurso:

   ```python
   from ...recursos import clima
   from ..servidor import rota

   @rota("GET", "/api/clima")
   def ver(pedido):
       return clima.PAINEIS["clima"]          # dict/list vira JSON 200; (404, {...}) muda o código
   ```

   Um `ValueError` dentro da rota vira 400 com a mensagem, e qualquer outro erro vira 500 e vai pro log.
   Por isso não precisa de try/except em toda rota.

3. **Comando de voz** (se fizer sentido) em `ultron/assistente/comandos.py`: uma função com `@comando` que
   devolve a frase de resposta, ou `None` se a fala não for com ela.

4. **Rotina** (se precisar rodar de tempos em tempos): coloque em `rotinas()`, no `ultron/app.py`.

5. **Teste** em `tests/`. Pelo menos: a função principal com um exemplo e a rota respondendo.

## Regras de código

- **Nomes em português**, que digam o que a coisa faz: `atualizar_tarefas`, `salvar_compromisso`.
- **Função curta**, que faz uma coisa. Se precisou de um comentário pra separar partes, provavelmente são duas funções.
- **Docstring de uma linha** em toda função pública, dizendo o que ela devolve ou o que muda.
- **Nada de dependência externa** sem um motivo muito bom: o projeto roda com `python server.py` e pronto.
- **Trabalho lento vai pra uma thread** (`threading.Thread(..., daemon=True)`), e a resposta pra tela sai antes.
  O Ultron precisa responder rápido.
- **Erro não derruba nada:** recurso que falha anota com `log_erro` e deixa o painel como estava.
- **Estado em disco** fica em `.estado/` (fora do git). Dados do dono (tarefas, provas, histórico) ficam na pasta
  dele (`ULTRON_PASTA`).
