# AJUDA

Este arquivo junta os problemas mais comuns do Lyra-Engine, o que eles significam e o que fazer sem ficar chutando.

## 1. O launcher para em `Instalando Ollama automaticamente...`

### O que significa

O Ollama ainda nao esta instalado ou o instalador ficou preso.

### O que fazer

1. Espere um pouco e acompanhe as mensagens do terminal.
2. Se demorar demais, confira o log em `%TEMP%\\Lyra_Ollama_Install.log`.
3. Se precisar, instale manualmente por [ollama.com/download/windows](https://ollama.com/download/windows).
4. Depois rode [start.bat](C:\Users\guell\Documents\gerador de musica\start.bat) de novo.

## 2. O Ollama sobe, mas a interface mostra modelo offline

### O que significa

O servico local pode estar online em `11434`, mas o modelo ainda nao foi baixado.

### O que fazer

1. Abra `Config`.
2. Escolha um modelo de texto.
3. Dispare o download pela interface.
4. Espere o status mudar para pronto.

## 3. O download do modelo parece interminavel

### O que significa

Modelos do Ollama baixam em partes e podem demorar bastante dependendo da internet e do disco.

### O que observar

- O terminal costuma mostrar linhas do tipo `downloading ...`.
- A interface consulta `GET /api/llm/status` em loop.
- O primeiro pull de modelo grande e realmente demorado.

### O que fazer

- Nao feche o Ollama no meio do pull.
- Prefira comecar com `Gemma 3 Gaia PT-BR 4B` ou `Qwen 3.5 4B`.

## 4. `GET /api/health` volta `503`

### O que significa

Normalmente quer dizer que o pipeline musical ainda esta carregando.

### Quando isso e normal

- no primeiro boot
- logo depois de reiniciar motores
- enquanto o ACE-Step esta preparando GPU

### Quando vira problema

Se continuar em `503` por muito tempo e nunca mudar para `200`.

### O que fazer

1. Espere o carregamento inicial.
2. Veja o terminal.
3. Se o pipeline nao subir, feche o app e rode [start.bat](C:\Users\guell\Documents\gerador de musica\start.bat) de novo.

## 5. O chat abre, mas nao responde ou mostra `Falha ao conversar com a IA`

### O que significa

O modelo pode nao estar carregado, o frontend pode estar em cache velho ou a resposta do stream pode ter falhado.

### O que fazer

1. Confirme em `Config` se o modelo esta pronto.
2. Reinicie o servidor.
3. Reabra `http://localhost:5000`.
4. Faca `Ctrl+F5`.
5. Tente um `Novo chat`.

## 6. O botao `Novo chat` ou a navegacao ficam estranhos

### O que significa

O frontend mudou bastante e o navegador pode estar usando JS antigo em cache.

### O que fazer

1. Pare o servidor.
2. Rode [start.bat](C:\Users\guell\Documents\gerador de musica\start.bat) de novo.
3. Faca `Ctrl+F5`.
4. Se ainda estiver zoado, abra a aba anonima e teste.

O historico do chat fica salvo localmente no navegador, entao conversas antigas quebradas podem continuar estranhas ate voce criar uma nova sessao.

## 7. O stream de letras nao aparece em tempo real

### O que significa

O backend pode ter caido no fallback JSON, ou o navegador nao abriu o stream.

### O que fazer

1. Confirme que o servidor foi reiniciado depois das ultimas mudancas.
2. Gere letras de novo.
3. Faca `Ctrl+F5`.
4. Veja se o texto aparece aos poucos na caixa de letras.

Se o modelo estiver pesado demais, a resposta pode demorar para comecar.

## 8. A musica sai curta, repetitiva ou com pouca estrutura

### O que significa

Isso costuma acontecer quando:

- a duracao esta curta demais
- a letra nao tem estrutura suficiente
- o prompt de estilo esta generico demais
- a referencia vocal esta fraca

### O que fazer

1. Use `90s`, `120s` ou `180s`.
2. Estruture a letra com tags como:
   - `[Intro]`
   - `[Verse]`
   - `[Pre-Chorus]`
   - `[Chorus]`
   - `[Bridge]`
   - `[Outro]`
3. Diga no prompt algo como `pop dançante, grande refrão, dois versos, pre-chorus crescente, refrão final maior`.
4. Se quiser letra longa, use `Longa` ou duracao maior.

## 9. A voz customizada fica ruim

### O que significa

O modelo ate aceita referencia vocal, mas a qualidade depende muito do audio enviado.

### O que ajuda de verdade

- referencia seca, sem muito reverb
- voz isolada ou com instrumental bem baixo
- arquivo curto e limpo
- mesma lingua e intencao da musica final

### O que piora bastante

- audio estourado
- muito eco
- instrumental brigando com a voz
- trecho longo demais e baguncado

## 10. O modelo de texto fica lento ou trava quando a musica esta gerando

### O que significa

Ollama e ACE-Step podem disputar VRAM e RAM.

### O que fazer

1. Espere a musica terminar antes de forcar conversa pesada.
2. Prefira modelos menores no dia a dia.
3. Se precisar, troque para `qwen3.5:4b`.
4. Evite deixar um modelo vision aberto sem necessidade.

## 11. O app parece recarregar paginas demais

### O que significa

O Lyra hoje usa shell unico com navegacao tipo SPA, mas o navegador ainda pode estar com cache antigo.

### O que fazer

1. Reinicie o servidor.
2. Abra a home.
3. Faca `Ctrl+F5`.

Depois disso:

- a navegacao principal nao deveria ficar recarregando tudo
- `Criar`, `Feed`, `Config` e `Chat` devem compartilhar o mesmo shell

## 12. Como fazer um reset rapido sem apagar musicas

### Passos

1. Feche o servidor.
2. Reabra [start.bat](C:\Users\guell\Documents\gerador de musica\start.bat).
3. Faca `Ctrl+F5`.
4. Se o problema for so de chat, use `Novo chat`.
5. Se o problema for so de modelo, troque o modelo em `Config`.

## 13. Se quiser me mandar erro para eu corrigir

Mande:

- print da tela
- trecho do terminal
- o que voce clicou antes do erro
- qual modelo estava selecionado
- se o erro aconteceu em `Criar`, `Feed`, `Config` ou `Chat`

## 14. Arquivos uteis para manutencao

- [README.md](C:\Users\guell\Documents\gerador de musica\README.md)
- [api.txt](C:\Users\guell\Documents\gerador de musica\api.txt)
- [app.py](C:\Users\guell\Documents\gerador de musica\app.py)
- [app.js](C:\Users\guell\Documents\gerador de musica\static\js\app.js)
- [chat_fix.js](C:\Users\guell\Documents\gerador de musica\static\js\chat_fix.js)
- [page_criar.html](C:\Users\guell\Documents\gerador de musica\templates\partials\page_criar.html)
