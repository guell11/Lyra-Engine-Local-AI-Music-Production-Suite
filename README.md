
# 🎵 Lyra Engine

<p align="center">
  <b>Gerador local de música com IA para Windows</b><br>
  <i>Sem nuvem. Sem dependência externa. Só você e sua GPU suando.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success">
  <img src="https://img.shields.io/badge/platform-Windows-blue">
  <img src="https://img.shields.io/badge/AI-local-orange">
  <img src="https://img.shields.io/badge/license-private-lightgrey">
</p>

---

## 🚀 Visão geral

O **Lyra Engine** é um sistema completo de geração musical com IA rodando **100% localmente**.

Ele integra:
- 🎼 Geração de música
- 🧠 Modelos de linguagem
- 🌐 Interface web local

<img width="2552" height="1263" alt="image" src="https://github.com/user-attachments/assets/a2cf654a-b2fd-4461-9738-5d08c5243090" />

🔗 **Acesse:**
```

[http://localhost:5000](http://localhost:5000)

````

---

## 🧠 Funcionalidades

- 🎶 Geração de música via prompt
- ✍️ Criação de letras com IA
- 💬 Chat musical em PT-BR
- 🌐 Pesquisa web integrada
- 📤 Exportação do chat → criação
- 🎤 Referência vocal
- 💾 Gerenciamento de faixas
- 🔁 Troca de modelos em tempo real
- 🧠 Controle de memória (VRAM/RAM)

---

## ⚙️ Stack

### 🎼 Música
- ACE-Step 1.5

### 🧾 Modelos de texto
- Gemma 3 Gaia PT-BR 4B  
- Gemma 3 Gaia PT-BR 4B Vision  
- Qwen 3.5 4B  
- Qwen 3.5 9B  

### 🧩 Runtime
- Ollama

### 🌐 Backend
- Flask

---

## ▶️ Como rodar

### 1. Execute:
```bash
start.bat
````

### 2. O sistema automaticamente:

* 🐍 Configura Python
* 🧱 Verifica Visual C++
* 🤖 Inicializa Ollama
* 🌐 Sobe servidor local

---

## 🧪 Modos de inicialização

| Script                     | Descrição                  |
| -------------------------- | -------------------------- |
| `start.bat`                | padrão                     |
| `start_CPU_Only.bat`       | sem GPU (dor emocional)    |
| `start_LowVRAM_GPU.bat`    | GPUs limitadas             |
| `start_Quantized_Fast.bat` | mais rápido, menos preciso |

---

## 🧭 Interface

### 🎨 Criar

* Prompt musical
* Letra
* Idioma
* Duração
* BPM
* Tonalidade
* Compasso
* Referência vocal

<img width="2552" height="1263" alt="image" src="https://github.com/user-attachments/assets/a2cf654a-b2fd-4461-9738-5d08c5243090" />


---

### 📚 Feed

* Biblioteca de faixas
* Player
* Delete
* Extend
* 
<img width="2557" height="1259" alt="image" src="https://github.com/user-attachments/assets/9ef4ba76-b2ec-45b6-8d9c-a0218f787212" />

---

### ⚙️ Config

* Modelo de texto
* Modelo vision
* Temperatura
* Repetição
* Idioma padrão
* Retenção de memória

<img width="2544" height="1269" alt="image" src="https://github.com/user-attachments/assets/ec763db8-a9c9-416c-948e-95c265ea44bd" />

---

### 💬 Chat

* Conversa com IA
* Pesquisa web
* Resposta em streaming
* Exportação para Criar
* 
<img width="2539" height="1261" alt="image" src="https://github.com/user-attachments/assets/eb5b69ad-c6b4-401f-89d0-b21fe40ab704" />

---

## 🎼 Formato musical

### Estrutura:

```txt
title:
style:
lyrics:
duration:
language:
```

### Regras

**Style**

```
[guitarra pesada metalica]
```

**Lyrics**

```
"Sol brilha no peito"
"Vento corta a estrada"
```

---

## 🧠 Retenção de memória

### Modos disponíveis

* `auto`
* `vram`
* `ram`
* `unload`

---

### 🎵 Comportamento

| Modo   | Descrição            |
| ------ | -------------------- |
| auto   | carrega sob demanda  |
| vram   | mais rápido, usa GPU |
| ram    | offload para CPU     |
| unload | descarrega sempre    |

---

## ⚠️ Notas importantes

* 🟡 “Pronto sob demanda” é normal
* ⏱️ Durações longas podem estourar VRAM
* 💡 Use `auto`, `ram` ou `unload` nesses casos
* 🌐 Chat pode usar busca real
* 🎨 Prompt vira consulta otimizada
* 🌎 Idioma exportado evita voz errada

---

## 📁 Estrutura

```bash
app.py
config.json
api.txt
README.md
AJUDA.md
static/
templates/
output/
models/
ace_step_src/
```

---

## 📚 Documentação

* `api.txt` → API
* `AJUDA.md` → troubleshooting
* `README.md` → documentação principal

---
---

## 🖥️ Requisitos de GPU (NVIDIA)

Este projeto foi **testado com placas NVIDIA**.

### 📊 VRAM recomendada

| Nível | VRAM | Observação |
|------|------|-----------|
| 🟢 Recomendado | **16 GB** | Experiência ideal, sem limitações |
| 🟡 Mínimo recomendado | **8 GB** | Funciona bem, com alguns cuidados |
| 🔴 Mínimo absoluto | **4 GB** | ⚠️ Por sua conta e risco |

---

### ⚠️ Observações importantes

- GPUs com **8 GB** podem ter problemas em:
  - músicas longas  
  - múltiplas gerações seguidas  

- GPUs com **4 GB**:
  - podem falhar frequentemente  
  - exigem modos como `ram` ou `unload`  
  - podem ser... uma experiência espiritual  

- Para evitar crashes:
  - prefira modos de memória mais leves  
  - reduza duração das faixas  
  - evite multitarefa pesada  

---


---

## 🧩 Tecnologias utilizadas

<p align="center">
  <img src="https://img.shields.io/badge/Flask-backend-black?logo=flask">
  <img src="https://img.shields.io/badge/Ollama-runtime-white?logo=llama">
  <img src="https://img.shields.io/badge/Python-3.x-blue?logo=python">
  <img src="https://img.shields.io/badge/NVIDIA-GPU-green?logo=nvidia">
  <img src="https://img.shields.io/badge/AI-Local-orange">
</p>

---

### 🧠 Stack detalhada

- 🌐 **Flask** → servidor web local  
- 🤖 **Ollama** → execução dos modelos  
- 🐍 **Python** → backend principal  
- 🎼 **ACE-Step 1.5** → geração musical  
- 🧾 **Gemma / Qwen** → linguagem e visão  

---

### ⚙️ Execução

Tudo roda localmente:

- sem API externa  
- sem dependência cloud  
- sem cobrança surpresa no cartão  

---

### 💡 Filosofia

> Seu PC, suas regras.  
> PRIVACIDADE é TUDO
