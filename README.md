Lyra-Engine
README em TXT

Atualizado em: 2026-04-09

==================================================
1. O que e
==================================================

Lyra-Engine e um gerador local de musica com IA para Windows.

Ele junta:
- ACE-Step 1.5 para gerar audio
- Ollama para chat, letras e visao
- Flask para servir a interface web local

Tudo roda na sua maquina.

Endereco padrao:
- http://localhost:5000

==================================================
2. O que o app faz hoje
==================================================

- gera musica a partir de prompt musical
- gera letras com IA local
- faz chat musical em PT-BR
- faz pesquisa web local guiada pelo chat
- exporta blocos do chat para a aba Criar
- aceita referencia vocal
- salva, toca, deleta e estende faixas
- troca modelos de texto e visao pela interface
- controla retencao de memoria para texto e musica

==================================================
3. Motores usados
==================================================

Musica:
- ACE-Step 1.5

Texto:
- Gemma 3 Gaia PT-BR 4B
- Gemma 3 Gaia PT-BR 4B Vision
- Qwen 3.5 4B
- Qwen 3.5 9B

Runtime de modelos:
- Ollama

==================================================
4. Como iniciar
==================================================

1. Rode start.bat
2. O launcher prepara o ambiente Python
3. O launcher verifica o Visual C++ Redistributable
4. O launcher instala ou inicia o Ollama
5. O app sobe em http://localhost:5000

Launchers extras:
- start.bat
- start_CPU_Only.bat
- start_LowVRAM_GPU.bat
- start_Quantized_Fast.bat

==================================================
5. Abas principais
==================================================

Criar:
- prompt musical
- letra
- idioma
- duracao
- BPM
- tonalidade
- compasso
- referencia vocal

Feed:
- biblioteca local das faixas geradas
- player
- delete
- extend

Config:
- modelo de texto
- modelo vision
- temperatura
- repeticao
- idioma padrao
- retencao de memoria

Chat:
- conversa com a IA
- pesquisa web
- resposta em stream
- exportar para Criar

==================================================
6. Formato musical do chat
==================================================

Quando o chat responde em modo musical, ele tenta usar blocos estruturados:

- title
- style
- lyrics
- duration
- language

Regras atuais:
- style em linhas com colchetes
  exemplo: [guitarra pesada metalica]
- lyrics com cada linha entre aspas
  exemplo: "Sol brilha no peito"

==================================================
7. Retencao de memoria
==================================================

Texto:
- auto
- vram
- ram
- unload

Musica:
- auto
- vram
- ram
- unload

Comportamento musical:

auto
- nao carrega o ACE-Step no boot
- entra em estado standby
- carrega sozinho quando voce clica em Criar Musica
- descarrega depois da geracao

vram
- deixa o modelo musical preso na GPU
- e o mais rapido para varias geracoes em sequencia
- pode faltar VRAM em faixas longas

ram
- usa offload para CPU/RAM quando possivel
- ajuda quando a GPU e mais apertada

unload
- descarrega tudo apos cada geracao

==================================================
8. Notas importantes de uso
==================================================

- Em modo automatico, o app pode mostrar "Pronto sob demanda".
  Isso e normal.

- Em duracoes altas, como 180s, o modo vram pode estourar VRAM.
  Nesses casos, prefira:
  - automatico
  - ram
  - unload

- O chat pode fazer pesquisa web para perguntas factuais e referencias musicais.

- Para pedidos criativos, a busca tenta transformar a frase do usuario em consultas reais de buscador.

- O idioma exportado do chat para Criar agora tenta ir junto para evitar voz errada.

==================================================
9. Arquivos importantes do projeto
==================================================

- app.py
- config.json
- api.txt
- README.md
- AJUDA.md
- static/
- templates/
- output/
- models/
- ace_step_src/

==================================================
10. Documentos recomendados
==================================================

- api.txt
  resumo da API real

- AJUDA.md
  ajuda e troubleshooting

- README.md
  versao markdown da documentacao principal

Fim.
