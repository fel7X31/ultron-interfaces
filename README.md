# Ultron

Um assistente de voz que **executa** em vez de só conversar. Você segura a barra de espaço (ou bate duas palmas), fala,
e ele usa o Claude Code dentro da sua pasta de trabalho pra consultar, anotar e agir nas suas ferramentas. Depois
responde em voz alta.

```
você fala → transcrição → Claude Code na sua pasta (skills, memória, conectores) → resposta falada → esfera reage
```

- **Ouvido:** whisper rodando no seu computador (grátis) ou ElevenLabs Scribe.
- **Cérebro:** uma sessão do Claude Code que fica aberta e lembra da conversa. Dá pra trocar o modelo (Sonnet, Opus,
  Haiku) ou pôr outra IA pra responder (ChatGPT, Gemini, Grok), no chip do meio do topo da tela ou por voz
  ("usa o Gemini").
- **Boca:** ElevenLabs ou Fish Audio.
- **Rosto:** uma esfera na tela, com painéis de e-mail, agenda, tarefas, mercado e música.
- **Comandos na hora:** "próxima música", "abre o currículo", "ativa o modo prova", "volume 30", "pausa o Spotify",
  "fecha o Discord" respondem sem passar pelo Claude.
- **Controle do PC:** volume, música, janelas, programas, brilho, Configurações do Windows e uso do PC (Windows).
- **Trava:** o que apaga, envia mensagem, publica ou desliga o PC só acontece depois que você diz "confirma".
- **Extras:** modo prova, tela de currículo (analisar e adaptar, exporta Word e PDF), histórico diário das conversas.

> Baseado no [JARVIS com Claude Code](https://github.com/matheustillimt-tech/jarvis), de Matheus Tilli (licença MIT).

## O que você precisa

- [Claude Code](https://claude.com/claude-code) instalado e logado (o comando `claude` funcionando no terminal).
- Python 3.9 ou mais novo. **O servidor não precisa de nenhuma biblioteca**: só a biblioteca padrão.
- Uma chave do [ElevenLabs](https://elevenlabs.io) (o plano grátis serve pra testar). Sem ela, ele responde só escrito.
- Opcional: `ffmpeg` e o whisper local, pra transcrição grátis.
- Opcional: `sounddevice` e `numpy`, só pra ligar com palmas (`palmas.py`).
- Opcional, pra usar outra IA além do Claude: entrar com a sua conta (Gemini com o Google, ChatGPT com a conta do
  ChatGPT, pelos programas deles) ou a chave da API (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`).

## Rodar no Windows

No PowerShell:

```powershell
git clone <url do repositório> ultron
cd ultron
copy .env.example .env
copy persona.example.md persona.md
notepad .env
```

1. No `.env`, coloque em `ULTRON_PASTA` a pasta que o Claude Code deve abrir (seu vault, suas notas ou um projeto)
   e em `ELEVENLABS_API_KEY` a sua chave.
2. No `persona.md`, preencha a parte **Sobre o dono**: quem é você, onde fica cada coisa na pasta e quais ferramentas
   estão ligadas. Quanto mais claro, mais rápido ele acerta.
3. Ligue:

   ```powershell
   py server.py
   ```

   Abre no navegador em `http://localhost:8790`. Na primeira vez, libere o microfone.

### Ligar com duas palmas (opcional)

```powershell
py -m pip install -r requirements-palmas.txt
py palmas.py --calibrar   # mostra o volume de cada som, pra ajustar
py palmas.py              # fica ouvindo; duas palmas ligam o Ultron em tela cheia
```

Pra ligar junto com o Windows, crie um atalho de `pythonw palmas.py` na pasta `shell:startup`.

### Outras IAs (opcional)

Dois jeitos, e dá pra misturar:

- **Com a sua conta, sem chave:** instale os programas deles (`npm install -g @google/gemini-cli @openai/codex`) e,
  no chip do meio do topo da tela, clique em **Entrar com Google** (Gemini) ou **Entrar com ChatGPT**. Abre um
  terminal com o login, e o navegador abre pra você entrar. É como o Claude Code: usa o plano da sua conta.
- **Com a chave da API:** coloque no `.env` a `OPENAI_API_KEY` (ChatGPT), a `GEMINI_API_KEY` (Gemini, tem plano grátis
  no [Google AI Studio](https://aistudio.google.com/apikey)) ou a `XAI_API_KEY` (Grok, só por chave). A chave vale
  mais que a conta.

Depois escolha no chip ou diga "usa o Gemini" / "volta pro Claude". Com outra IA ele só conversa (sem ferramentas); os
comandos na hora continuam valendo. O modelo de cada uma muda no `.env` (`ULTRON_MODELO_CHATGPT`,
`ULTRON_MODELO_GEMINI`, `ULTRON_MODELO_GROK`).

**Quando o limite acaba:** se quem responde chega no limite de uso do plano (o de 5 horas ou o da semana do Claude, a
cota do ChatGPT ou do Gemini), o Ultron anota até quando, passa pra próxima que ainda tem e responde a mesma pergunta
com ela, avisando: "O Claude chegou no limite de uso, libera às 15:00. Passei pro ChatGPT." A ordem é a que você
escolheu, depois o Claude (o seu modelo e os outros, porque ele tem ferramentas) e depois ChatGPT, Gemini e Grok.
Quando o limite libera, ele volta sozinho pra que você escolheu. A lista de IAs mostra "sem limite, volta às 15:00"
em cada uma que chegou; escolher uma dessas na mão faz ele tentar de novo. Fica anotado em `.estado/limites.json`.

### Whisper local (opcional)

Sem ele, o Ultron usa o ElevenLabs Scribe sozinho (`ULTRON_TRANSCRICAO=auto`). Pra transcrever de graça:

1. Instale o ffmpeg: `winget install ffmpeg`.
2. Baixe o [whisper.cpp](https://github.com/ggerganov/whisper.cpp/releases) e o modelo
   [`ggml-large-v3-turbo.bin`](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin).
3. Rode `whisper-server -m ggml-large-v3-turbo.bin --host 127.0.0.1 --port 8178 -l pt`.

### No Mac ou Linux

Igual, trocando `copy` por `cp` e `py` por `python3`. No Mac, `brew install whisper-cpp ffmpeg`, e
`bash app/montar.sh` monta um app com ícone próprio.

## Usar

| Tecla | O que faz |
|---|---|
| Segurar **espaço** | Fala com ele. Apertar de novo enquanto ele fala ou pensa **interrompe** na hora |
| **T** | Digita em vez de falar |
| **N** | Começa uma conversa nova |
| **H** | Mostra ou esconde os detalhes |

No chip do meio do topo você escolhe quem responde (Claude ou outra IA). Na engrenagem, a voz (lista em
`vozes.json`), a velocidade, o seu nome, o modo texto e o modo prova.
Fica salvo em `.estado/preferencias.json`, que vale mais que o `.env`.

## A trava

Antes de cada ação, o `hooks/trava.py` decide:

- **Passa direto:** ler, buscar, pesquisar, consultar conectores, controlar o PC e criar ou editar arquivos em
  qualquer lugar da sua pasta de usuário (inclusive o código do próprio Ultron).
- **Precisa de confirmação:** ação de conector que cria, envia, salva, apaga ou publica; escrever fora da pasta de
  usuário ou nas pastas de configuração (AppData e as que começam com ponto); comandos de terminal que apagam, fecham
  programa à força, desligam o PC, publicam ou mandam dados pra fora.
- **Nunca:** mudar a própria trava (`hooks/`) ou o `.env`.

Cada ação barrada fica anotada em `.estado/trava.jsonl`, pra você ver o que a trava segurou.

O Ultron edita o próprio código quando você pede, sem pedir confirmação. Cada mudança fica registrada em
`MUDANCAS-ULTRON.md` (pedido, antes, depois e backup), pelo `hooks/registro.py`.

É uma lista de proteção, não uma caixa de areia. Leia o `hooks/trava.py` antes de liberar ferramentas novas.

## Atalhos e pré-busca

Pergunta que se repete fica mais rápida com um script em `atalhos/` que devolve a resposta numa linha só
(ex.: `mercado.py`, com dólar, euro, bitcoin e bolsas). Em `gatilhos.json`, cada palavra aponta pra um atalho:
quando você fala "dólar", o atalho roda na hora e o dado já vai junto com a pergunta.

## Velocidade

Pergunta simples sai em 1 a 2 segundos; com dado, 3 a 6. O que mais ajuda:

- `ULTRON_CONTEXTO=leve` (padrão): o Claude abre numa pasta vazia com a sua pasta anexada, sem carregar o
  CLAUDE.md dela a cada pergunta.
- `ULTRON_MODELO=sonnet` e `ULTRON_ESFORCO=low` (padrão).
- Atalhos e pré-busca pras perguntas frequentes.
- `ULTRON_MODELO_VOZ=eleven_flash_v2_5` começa a falar ~1 s antes, com voz um pouco pior.

## Custos

- **Claude Code:** usa o seu plano. Cada pergunta é uma mensagem; os painéis de e-mail e agenda fazem uma consulta a
  cada `ULTRON_PAINEIS_MIN` minutos (0 desliga).
- **ElevenLabs:** cobra por caractere falado (uma resposta curta tem uns 150).
- **Whisper local:** grátis.

## Para quem vai mexer no código

O backend fica em `ultron/`, em camadas. Cada funcionalidade é um arquivo em `ultron/recursos/`, as rotas ficam em
`ultron/http/rotas/` e os comandos de voz em `ultron/assistente/comandos.py`. O mapa completo, o caminho de uma fala
e o passo a passo pra criar uma funcionalidade nova estão em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

Testes (não abrem o Claude nem chamam serviços de fora):

```powershell
py -m unittest discover -s tests -v
```

```
server.py          ponto de entrada (chama ultron/app.py)
ultron/            o backend (veja docs/ARQUITETURA.md)
web/               a tela (HTML/CSS/JS, sem build)
hooks/             trava.py e registro.py
atalhos/           scripts de resposta rápida
palmas.py          liga com duas palmas
persona.example.md a personalidade (copie pra persona.md)
vozes.json         as vozes da engrenagem
gatilhos.json      palavras que já disparam um atalho
tests/             testes
.estado/           logs, caches e backups (fora do git)
```

## Licença

MIT. Veja [LICENSE](LICENSE).
