<div align="center">

# Lyra Engine

### Local AI Music Generation Platform

**A fully local AI music generation environment that combines music synthesis, language models, multimodal capabilities and GPU-aware model orchestration in a single interface.**

`Windows` · `Python` · `Flask` · `ACE-Step` · `Ollama` · `Gemma` · `Qwen`

<br>

<img src="https://img.shields.io/badge/status-active-success">
<img src="https://img.shields.io/badge/platform-Windows-blue">
<img src="https://img.shields.io/badge/inference-local-orange">
<img src="https://img.shields.io/badge/GPU-NVIDIA-76B900?logo=nvidia">
<img src="https://img.shields.io/badge/license-private-lightgrey">

</div>

---

## Overview

**Lyra Engine** is a local-first environment for AI-assisted music creation.

It combines a music generation model, local language models and a web application into a unified workflow where users can move from an idea to a generated track without relying on cloud inference.

The system handles more than generation itself.

It orchestrates:

* music synthesis;
* prompt and lyric generation;
* local LLM inference;
* multimodal models;
* model lifecycle management;
* GPU and system memory allocation;
* track storage;
* streaming chat;
* web-assisted research;
* creation workflows.

Everything is exposed through a local web interface while the inference stack remains on the user's machine.

> **Local models. Local files. Local inference.**

---

## Interface

### Create

The creation workspace provides control over the main musical parameters:

* musical prompt;
* lyrics;
* language;
* duration;
* BPM;
* key;
* time signature;
* vocal reference.

<img width="2552" height="1263" alt="Lyra Engine creation interface" src="https://github.com/user-attachments/assets/a2cf654a-b2fd-4461-9738-5d08c5243090" />

---

### Library

Generated tracks are stored in a local library with integrated playback and management.

Available actions include:

* playback;
* deletion;
* track extension;
* access to previous generations.

<img width="2557" height="1259" alt="Lyra Engine track library" src="https://github.com/user-attachments/assets/9ef4ba76-b2ec-45b6-8d9c-a0218f787212" />

---

### AI Configuration

Language and vision inference can be configured directly from the interface.

The application exposes controls for:

* text model;
* vision model;
* temperature;
* repetition parameters;
* default language;
* model memory retention.

<img width="2544" height="1269" alt="Lyra Engine AI configuration" src="https://github.com/user-attachments/assets/ec763db8-a9c9-416c-948e-95c265ea44bd" />

---

### AI Chat

Lyra also provides a local AI assistant integrated with the music creation workflow.

It supports:

* local LLM conversations;
* PT-BR interaction;
* streaming responses;
* web search;
* musical ideation;
* prompt development;
* direct transfer from conversation to the creation workspace.

<img width="2539" height="1261" alt="Lyra Engine AI chat" src="https://github.com/user-attachments/assets/eb5b69ad-c6b4-401f-89d0-b21fe40ab704" />

---

## Architecture

```text
                         Lyra Engine
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        Web Interface     Flask Backend    Local Storage
              │               │               │
              └───────────────┤               │
                              │               │
                ┌─────────────┴─────────────┐ │
                │                           │ │
                ▼                           ▼ ▼
          LLM Runtime                 Music Engine
            Ollama                    ACE-Step 1.5
                │                           │
       ┌────────┴────────┐                  │
       │                 │                  │
       ▼                 ▼                  ▼
    Gemma              Qwen           Audio generation
       │                 │                  │
       └────────┬────────┘                  │
                │                           │
                ▼                           ▼
       Text / Vision AI              Generated tracks
                │                           │
                └─────────────┬─────────────┘
                              ▼
                       Local workspace
```

The application acts as an orchestration layer between the user interface, local language models and the music generation pipeline.

---

## Core features

### AI music generation

Music can be generated from structured parameters including textual descriptions, lyrics, duration, tempo, tonality and language.

ACE-Step 1.5 provides the underlying music generation pipeline.

### AI-assisted songwriting

Local language models can transform an initial concept into:

* lyrics;
* song structures;
* musical descriptions;
* refined generation prompts.

The resulting content can be transferred directly into the creation workflow.

### Local multimodal inference

Lyra supports configurable text and vision models through Ollama.

Current model options include:

* Gemma 3 Gaia PT-BR 4B;
* Gemma 3 Gaia PT-BR 4B Vision;
* Qwen 3.5 4B;
* Qwen 3.5 9B.

Models can be changed without rebuilding the application.

### Integrated research

The assistant can optionally use web search to gather external information before generating a response.

This allows research and music creation to remain inside the same workflow.

### Vocal reference

The generation pipeline supports vocal reference input as part of the creation process.

### Track management

Generated material is organized locally and can be played, managed and reused through the application interface.

---

## Memory-aware inference

Running music generation and language models on the same machine creates an important engineering problem:

**VRAM is finite.**

Lyra includes explicit model-retention strategies to control where models remain between operations.

| Mode     | Behavior                                           |
| -------- | -------------------------------------------------- |
| `auto`   | selects resources according to demand              |
| `vram`   | prioritizes GPU residency and lower reload latency |
| `ram`    | offloads models to system memory when possible     |
| `unload` | releases models aggressively between operations    |

This allows the same application to target systems with very different hardware constraints.

```text
                    Model requested
                          │
                          ▼
                  Memory strategy
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
        VRAM             RAM            Unload
          │               │               │
          ▼               ▼               ▼
     Low latency     Lower VRAM use   Minimum retention
```

---

## GPU requirements

The project has been tested with **NVIDIA GPUs**.

| Configuration    |       VRAM | Expected experience                                    |
| ---------------- | ---------: | ------------------------------------------------------ |
| Recommended      | **16 GB+** | Full workflow with fewer memory constraints            |
| Supported target |   **8 GB** | Usable with memory management                          |
| Constrained      |   **4 GB** | Requires aggressive offloading and shorter generations |

VRAM usage depends on factors including:

* selected models;
* track duration;
* quantization;
* model retention strategy;
* simultaneous workloads.

Systems with limited VRAM should prefer `auto`, `ram` or `unload`.

---

## Model orchestration

One of the main responsibilities of Lyra is coordinating multiple AI workloads on a single workstation.

```text
User request
     │
     ▼
Lyra backend
     │
     ├── textual task ──────► Ollama ──────► LLM
     │
     ├── vision task ───────► Ollama ──────► Vision model
     │
     └── music task ────────► ACE-Step ────► Audio
                                  │
                                  ▼
                           Track management
```

The memory controller determines when models should remain loaded, move away from GPU memory or be released entirely.

This is especially important when music synthesis and LLM inference compete for the same GPU.

---

## Music generation format

Internally, creation requests can be represented using structured musical information:

```text
title:
style:
lyrics:
duration:
language:
```

For example:

```text
title: Night Drive
style: atmospheric synthwave, analog bass, cinematic drums
lyrics:
  "City lights dissolve behind me"
  "Midnight running through the glass"
duration: 180
language: en
```

Separating semantic information from generation parameters makes it easier for the AI assistant and creation interface to share the same pipeline.

---

## Startup profiles

Lyra provides different execution profiles for different hardware configurations.

| Script                     | Profile                     |
| -------------------------- | --------------------------- |
| `start.bat`                | standard execution          |
| `start_CPU_Only.bat`       | CPU-oriented fallback       |
| `start_LowVRAM_GPU.bat`    | reduced VRAM usage          |
| `start_Quantized_Fast.bat` | quantized inference profile |

For the standard configuration:

```bat
start.bat
```

The launcher handles the local environment and starts the services required by the application.

Once initialized, the interface is available at:

```text
http://localhost:5000
```

---

## Technology stack

| Layer             | Technology           |
| ----------------- | -------------------- |
| Music generation  | **ACE-Step 1.5**     |
| Language models   | **Gemma / Qwen**     |
| Local LLM runtime | **Ollama**           |
| Backend           | **Python / Flask**   |
| Interface         | **Web UI**           |
| Acceleration      | **NVIDIA GPU**       |
| Storage           | **Local filesystem** |

---

## Repository structure

```text
Lyra/
├── app.py
│
├── config.json
├── api.txt
├── AJUDA.md
├── README.md
│
├── static/
│   └── frontend assets
│
├── templates/
│   └── application interface
│
├── output/
│   └── generated tracks
│
├── models/
│   └── local model resources
│
└── ace_step_src/
    └── music generation runtime
```

---

## Local-first design

Lyra was designed around local execution rather than treating it as a fallback mode.

The core inference workflow does not require cloud-hosted model APIs.

This provides several practical properties:

### Privacy

Prompts, lyrics, model interactions and generated tracks can remain on the local machine.

### Predictable inference cost

Local generation does not introduce per-request inference API charges.

### Model control

The user controls which models are installed and executed.

### Offline-capable inference

Once the required models and dependencies are available locally, core model inference does not depend on a remote inference service.

Web-search functionality naturally requires network access when enabled.

---

## Engineering focus

Lyra is not only a frontend around a music model.

The project explores the engineering required to combine several resource-intensive AI systems inside one local application:

* heterogeneous model orchestration;
* GPU memory pressure;
* model loading and unloading;
* quantized inference;
* streaming generation;
* multimodal interaction;
* persistent local media;
* workflow integration between LLM output and generative audio.

The central challenge is making those components behave as **one application** rather than a collection of unrelated inference scripts.

---

## Documentation

Additional project documentation:

* `api.txt` — API reference;
* `AJUDA.md` — troubleshooting and operational notes;
* `README.md` — project overview.

---

## Project status

**Active development.**

Current functionality includes:

* local music generation;
* local text inference;
* vision model integration;
* streaming AI chat;
* optional web research;
* AI-assisted lyrics and prompts;
* vocal references;
* configurable model selection;
* track library;
* memory-aware model management;
* multiple hardware profiles.

The project currently targets Windows and NVIDIA-based systems.

---

## Philosophy

> **Your machine. Your models. Your music.**

Lyra is built around the idea that a complete generative AI workspace can run locally while still providing the convenience expected from modern AI applications.

No mandatory cloud inference layer between the creator and the models.

---

<div align="center">

### Lyra Engine

**Local AI for music creation, from the first idea to the generated track.**

</div>
