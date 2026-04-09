"""
Lyra-Engine — AI-Powered Music & Lyrics Generator
Backend: ACE-Step 1.5 (music) + Gemma 2B GGUF (lyrics via llama-cpp-python)
"""

import os
import sys
import json
import time
import logging
import threading
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlparse

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context
import requests

# ── Configuration ─────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"
FLASK_PORT = 5000

AVAILABLE_LLMS = {
    "gaia_text_4b": {
        "title": "Gemma 3 Gaia PT-BR 4B",
        "model": "cnmoro/gemma3-gaia-ptbr-4b:q4_k_m",
        "size": "2.5 GB",
        "kind": "text",
        "description": "Texto em PT-BR para chat, letras e briefing musical.",
    },
    "gaia_vision_4b": {
        "title": "Gemma 3 Gaia PT-BR 4B Vision",
        "model": "cnmoro/gemma3-gaia-ptbr-4b-vision:q4_k_m",
        "size": "2.7 GB",
        "kind": "vision",
        "description": "Vision para imagem + texto em PT-BR via Ollama.",
    },
    "qwen35_4b": {
        "title": "Qwen 3.5 4B",
        "model": "qwen3.5:4b",
        "size": "3.4 GB",
        "kind": "text",
        "description": "Modelo leve e rapido para conversa e ideacao.",
    },
    "qwen35_9b": {
        "title": "Qwen 3.5 9B",
        "model": "qwen3.5:9b",
        "size": "7.2 GB",
        "kind": "text",
        "description": "Modelo maior para respostas mais consistentes.",
    },
}
CONFIG_FILE     = BASE_DIR / "config.json"

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("aura-studio")

# ── Flask App ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

# Global state
pipeline = None
llm_model = None
loaded_llm_id = None
llm_lock = threading.Lock()
llm_downloading = False
llm_last_error = None
llm_runtime_notice = None
llm_pull_status = {}
ollama_start_lock = threading.Lock()

setup_state = {
    "phase":    "idle",
    "message":  "",
    "current":  0,
    "total":    0,
    "complete": False,
    "error":    None,
}

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_KEEP_ALIVE_CHAT = os.environ.get("LYRA_OLLAMA_KEEP_ALIVE_CHAT", "10m")
OLLAMA_KEEP_ALIVE_LYRICS = os.environ.get("LYRA_OLLAMA_KEEP_ALIVE_LYRICS", "0")
WEB_RESEARCH_SEARCH_URL = "https://html.duckduckgo.com/html/"
WEB_RESEARCH_DDG_INSTANT_URL = "https://api.duckduckgo.com/"
WEB_RESEARCH_GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"
WEB_RESEARCH_FETCH_CHARS = 5000
WEB_RESEARCH_DEFAULT_LEVEL = "basic"
WEB_RESEARCH_GOOGLE_API_KEY = os.environ.get("LYRA_GOOGLE_SEARCH_API_KEY", "").strip()
WEB_RESEARCH_GOOGLE_CSE_ID = os.environ.get("LYRA_GOOGLE_SEARCH_CSE_ID", "").strip()
WEB_RESEARCH_LEVELS = {
    "basic": {
        "title": "Basico",
        "max_sites": 5,
        "query_count": 3,
        "results_per_query": 3,
    },
    "medium": {
        "title": "Medio",
        "max_sites": 10,
        "query_count": 4,
        "results_per_query": 4,
    },
    "large": {
        "title": "Grande",
        "max_sites": 20,
        "query_count": 6,
        "results_per_query": 5,
    },
}
WEB_RESEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-CH-UA": '"Google Chrome";v="135", "Chromium";v="135", "Not.A/Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}
DEFAULT_TEXT_LLM_ID = "gaia_text_4b"
DEFAULT_VISION_LLM_ID = "gaia_vision_4b"
DEFAULT_APP_CONFIG = {
    "theme": "light",
    "llm_temperature": 1.05,
    "llm_repeat_penalty": 1.5,
    "llm_model_id": DEFAULT_TEXT_LLM_ID,
    "llm_vision_model_id": DEFAULT_VISION_LLM_ID,
    "basePrompt": "",
    "maxTokens": 1024,
    "defaultLang": "pt",
    "defaultDuration": 90,
    "defaultSteps": 25,
    "acestep_vram_mode": "vram",
    "gemma_vram_mode": "ram",
}

RETENTION_POLICIES = {"auto", "vram", "ram", "unload"}
RESEARCH_STOPWORDS = {
    "quem", "qual", "quais", "como", "onde", "quando", "porque", "por", "que",
    "para", "pra", "das", "dos", "del", "de", "do", "da", "e", "o", "a", "os",
    "as", "um", "uma", "uns", "umas", "sobre", "com", "sem", "no", "na", "nos",
    "nas", "em", "ao", "aos", "ser", "foi", "era", "sao", "e", "eh",
}
RESEARCH_SOFT_TERMS = {
    "biografia", "discografia", "entrevista", "estilo", "musical", "musicais",
    "influencia", "influencias", "analise", "producao", "voz", "vocal",
    "tecnica", "tecnicas", "instrumentacao", "letras", "tema", "temas",
    "pesquisa", "pesquisar", "pesquise", "procure", "procurar", "fala",
    "falar", "diga", "me", "artista", "banda", "bandas", "cantor", "cantora",
    "grupo", "musica", "musicas", "album", "albuns", "disco", "discos",
    "historia", "origem", "resumo", "sobre", "nome", "melhor", "melhores",
    "refrao", "refroes", "arranjo", "arranjos", "referencia", "referencias",
    "inspiracao", "inspiracoes", "compor", "composta", "composicao", "composicoes",
    "criar", "crie", "gera", "gerar", "escrever", "escreva", "ajude", "ajuda",
    "quero", "preciso", "ritmo", "ritimo", "genero", "sonoridade", "pegada",
    "ideia", "ideias",
}
MUSIC_CREATION_MARKERS = [
    "cria uma musica", "criar uma musica", "compoe", "compor", "compõe",
    "cria musica", "criar musica", "crie uma musica", "crie musica",
    "cria 1 musica", "crie 1 musica", "faz 1 musica", "faz um som",
    "escreve uma letra", "escrever uma letra", "gera uma letra", "gerar uma letra",
    "faz uma musica", "faça uma musica", "faca uma musica", "transforma em musica",
    "transforme em musica", "me da uma letra", "me de uma letra", "refrao", "refrão",
    "verso", "pre-chorus", "chorus", "bridge", "arranjo", "arrangement", "bpm",
    "style", "lyrics", "title", "duration", "exporta", "exportar para criar",
    "briefing musical", "prompt musical",
]
INFORMATIONAL_MARKERS = [
    "quem e", "quem foi", "o que e", "o que foi", "qual e", "quais sao",
    "como e", "como foi", "quando", "onde", "por que", "porque",
    "pesquisa", "pesquise", "procura", "procure", "resuma", "resumir",
    "explica", "explique", "me diga", "fale sobre", "fala sobre",
    "me conta", "biografia", "discografia", "entrevista",
    "letras de", "musicas de", "ritmo de", "ritmos de", "ritimo de", "ritimos de",
    "estilo de", "influencias de", "influencias do",
]
EXPLICIT_WEB_RESEARCH_MARKERS = [
    "pesquisa", "pesquise", "procura", "procure", "busque", "busca",
    "quem e", "quem foi", "o que e", "qual e", "quais sao", "biografia",
    "discografia", "entrevista", "inspirado em", "inspirada em",
    "estilo de", "influencias de", "influencias do", "referencia de",
    "referencias de", "como soa", "como e o estilo",
    "letras de", "musicas de", "ritmo de", "ritmos de", "ritimo de", "ritimos de",
]
CREATIVE_SEARCH_NOISE_TERMS = {
    "ajude", "ajuda", "me", "compor", "compoe", "composta", "composicao",
    "criar", "crie", "cria", "gera", "gerar", "escreva", "escrever",
    "quero", "preciso", "tipo", "estilo", "sonoridade", "pegada",
    "musica", "musical", "musicas", "letra", "letras", "refrao", "refroes",
    "verso", "versos", "bridge", "chorus", "intro", "outro", "hook",
    "tema", "temas", "pesquisa", "pesquise", "procura", "procure",
    "busca", "busque", "melhor", "melhores", "genero", "generos", "do", "da",
}
MUSIC_STYLE_HINT_TERMS = {
    "pop", "rock", "metal", "metaleiro", "metalico", "metalica", "indie",
    "punk", "hardcore", "trap", "funk", "sertanejo", "pagode", "samba",
    "mpb", "jazz", "blues", "eletronico", "eletronica", "synthpop",
    "sintetizado", "lofi", "lo-fi", "hyperpop", "emo", "gospel", "rnb",
    "soul", "reggae", "forro", "brega", "drill", "phonk", "grunge",
    "shoegaze", "alternativo", "animado", "energetico", "energica",
    "pesado", "pesada", "agressivo", "agressiva", "romantico", "romantica",
    "sombrio", "sombria", "tropical", "dançante", "dancante",
}


def normalize_retention_policy(value, default="ram"):
    normalized = str(value or "").strip().lower()
    return normalized if normalized in RETENTION_POLICIES else default


def get_text_retention_policy(cfg=None):
    cfg = cfg or load_app_config()
    return normalize_retention_policy(cfg.get("gemma_vram_mode"), default="ram")


def get_music_retention_policy(cfg=None):
    cfg = cfg or load_app_config()
    return normalize_retention_policy(cfg.get("acestep_vram_mode"), default="vram")


def resolve_vocal_language(value=None, cfg=None):
    cfg = cfg or load_app_config()
    raw_value = str(value or cfg.get("defaultLang") or "pt").strip().lower()
    normalized = ascii_fold(raw_value)
    mapping = {
        "pt": "pt",
        "pt-br": "pt",
        "portugues": "pt",
        "portuguese": "pt",
        "en": "en",
        "english": "en",
        "ingles": "en",
        "es": "es",
        "spanish": "es",
        "espanhol": "es",
        "fr": "fr",
        "french": "fr",
        "frances": "fr",
        "ja": "ja",
        "japanese": "ja",
        "japones": "ja",
        "ko": "ko",
        "korean": "ko",
        "coreano": "ko",
    }
    if normalized in mapping:
        return mapping[normalized]
    if re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", normalized):
        return normalized.split("-", 1)[0]
    fallback = ascii_fold(str(cfg.get("defaultLang") or "pt").strip().lower())
    return mapping.get(fallback, "pt")


def resolve_ollama_keep_alive(cfg=None):
    mode = get_text_retention_policy(cfg)
    if mode == "vram":
        return "45m"
    if mode == "ram":
        return "8m"
    if mode == "auto":
        return "90s"
    return "0"


def build_ollama_runtime_options(*, max_tokens, temperature, repeat_penalty, stop=None, cfg=None):
    cfg = cfg or load_app_config()
    options = {
        "temperature": temperature,
        "repeat_penalty": repeat_penalty,
        "num_predict": max_tokens,
    }
    if stop:
        options["stop"] = stop

    try:
        import torch
        if torch.cuda.is_available():
            options["main_gpu"] = 0
            options["num_gpu"] = -1
    except Exception:
        pass

    return options


def should_unload_text_model(cfg=None):
    return get_text_retention_policy(cfg) == "unload"


def should_lazy_load_music_model(cfg=None):
    return get_music_retention_policy(cfg) in {"auto", "unload"}


def should_unload_music_model(cfg=None):
    return get_music_retention_policy(cfg) in {"auto", "unload"}


def sanitize_llm_text(text):
    if not text:
        return ""
    cleaned = str(text)
    cleaned = cleaned.replace("<bos>", "")
    cleaned = cleaned.replace("<start_of_turn>user", "")
    cleaned = cleaned.replace("<start_of_turn>model", "")
    cleaned = cleaned.replace("<end_of_turn>", "")
    cleaned = cleaned.replace("<|endoftext|>", "")
    cleaned = cleaned.replace("<think>", "")
    cleaned = cleaned.replace("</think>", "")
    cleaned = re.sub(r"<\|[^>]+\|>", "", cleaned)
    return cleaned.strip()


def strip_markdown_code_fence(text):
    if not text:
        return ""
    cleaned = str(text).strip()
    match = re.fullmatch(r"```[^\n]*\n(.*?)\n```", cleaned, flags=re.S)
    if match:
        return match.group(1).strip()
    return cleaned


def ascii_fold(text):
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_section_tag(raw_label):
    if not raw_label:
        return None

    label = sanitize_llm_text(raw_label)
    label = label.replace("*", " ").replace("_", " ").replace("`", " ")
    label = re.sub(r"\b\d+\s*(?:s|sec|secs|seg|segs|segundo|segundos)\b", " ", label, flags=re.I)
    label = re.sub(r"\s+", " ", label).strip(" -:|[](){}")
    if not label:
        return None

    folded = ascii_fold(label).lower()
    number_match = re.search(r"\b(\d+)\b", folded)
    section_number = number_match.group(1) if number_match else None

    if "pre" in folded and ("chorus" in folded or "refrao" in folded):
        return "[Pre-Chorus]"
    if "final" in folded and ("chorus" in folded or "refrao" in folded):
        return "[Final Chorus]"
    if "chorus" in folded or "refrao" in folded:
        return "[Chorus]"
    if "bridge" in folded or "ponte" in folded:
        return "[Bridge]"
    if "hook" in folded:
        return "[Hook]"
    if "outro" in folded or "encerramento" in folded or folded == "final":
        return "[Outro]"
    if "intro" in folded or "introducao" in folded:
        return "[Intro]"
    if "instrumental" in folded or re.fullmatch(r"inst(?:rumental)?", folded):
        return "[inst]"
    if "vocal" in folded:
        return "[vocal]"
    if "verse" in folded or "verso" in folded or "estrofe" in folded:
        if section_number:
            return f"[Verse {section_number}]"
        return "[Verse]"
    return None


def normalize_generation_caption(caption):
    if not caption:
        return ""

    cleaned = sanitize_llm_text(strip_markdown_code_fence(caption))
    cleaned = re.sub(r"[*_`#>]+", " ", cleaned)
    cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", cleaned, flags=re.M)
    cleaned = re.sub(r"\s*\n+\s*", ", ", cleaned)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip(" ,")
    return cleaned


def normalize_generation_lyrics(lyrics):
    if not lyrics:
        return ""

    cleaned = sanitize_llm_text(strip_markdown_code_fence(lyrics))
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    normalized_lines = []
    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if not line:
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            continue

        heading_candidate = line
        heading_candidate = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", heading_candidate)
        heading_candidate = heading_candidate.strip()

        if heading_candidate.startswith("(") and heading_candidate.endswith(")"):
            heading_candidate = heading_candidate[1:-1].strip()

        heading_candidate = re.split(r"\s+-\s+|:\s+", heading_candidate, maxsplit=1)[0].strip()
        heading_tag = normalize_section_tag(heading_candidate)

        if heading_tag:
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            normalized_lines.append(heading_tag)
            continue

        inline_tag_match = re.match(r"^\[(.+?)\]\s+(.+)$", line)
        if inline_tag_match:
            inline_tag = normalize_section_tag(inline_tag_match.group(1))
            if inline_tag:
                if normalized_lines and normalized_lines[-1] != "":
                    normalized_lines.append("")
                normalized_lines.append(inline_tag)
                line = inline_tag_match.group(2).strip()

        line = strip_wrapping_quotes(re.sub(r"[*_`]+", "", line).strip())
        normalized_lines.append(line)

    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()

    body = "\n".join(normalized_lines).strip()
    if not body:
        return ""

    if not re.match(r"^\[(?:vocal|inst)\]", body, flags=re.I):
        body = "[vocal]\n" + body

    return body


def is_cuda_available():
    try:
        import torch
        free_llm()
        return torch.cuda.is_available()
    except Exception:
        return False


def get_default_llm_id(kind="text"):
    preferred = DEFAULT_VISION_LLM_ID if kind == "vision" else DEFAULT_TEXT_LLM_ID
    if preferred in AVAILABLE_LLMS and AVAILABLE_LLMS[preferred].get("kind") == kind:
        return preferred

    for model_id, model_info in AVAILABLE_LLMS.items():
        if model_info.get("kind") == kind:
            return model_id

    return next(iter(AVAILABLE_LLMS.keys()))


def resolve_llm_target(cfg=None, kind="text"):
    cfg = cfg or load_app_config()
    config_key = "llm_vision_model_id" if kind == "vision" else "llm_model_id"
    requested_id = cfg.get(config_key, get_default_llm_id(kind))
    if requested_id not in AVAILABLE_LLMS:
        requested_id = get_default_llm_id(kind)

    requested_info = AVAILABLE_LLMS[requested_id]
    if kind == "text":
        return requested_id, requested_id, None
    if requested_info.get("kind") == kind:
        return requested_id, requested_id, None

    fallback_id = get_default_llm_id(kind)
    return (
        fallback_id,
        requested_id,
        f"{requested_info['title']} nao e um modelo de {kind}. "
        f"Usando {AVAILABLE_LLMS[fallback_id]['title']} automaticamente.",
    )


def find_ollama_executable():
    env_bin = os.environ.get("OLLAMA_BIN", "").strip()
    candidates = []
    if env_bin:
        candidates.append(env_bin)

    which_bin = shutil.which("ollama")
    if which_bin:
        candidates.append(which_bin)

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates.extend([
        local_app_data / "Programs" / "Ollama" / "ollama.exe",
        local_app_data / "Programs" / "Ollama" / "ollama app.exe",
    ])

    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return str(candidate_path)

    return None


def is_ollama_running(timeout=2):
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=timeout)
        response.raise_for_status()
        return True
    except Exception:
        return False


def get_ollama_version():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=3)
        response.raise_for_status()
        return response.json().get("version")
    except Exception:
        return None


def start_ollama_background():
    if is_ollama_running():
        return True

    ollama_exe = find_ollama_executable()
    if not ollama_exe:
        raise RuntimeError("Ollama nao foi encontrado. Rode o launcher atualizado para instalar automaticamente.")

    with ollama_start_lock:
        if is_ollama_running():
            return True

        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            creationflags = 0
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            kwargs["creationflags"] = creationflags
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen([ollama_exe, "serve"], **kwargs)
        return True


def ensure_ollama_service(timeout=15):
    if is_ollama_running():
        return True

    start_ollama_background()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_ollama_running():
            return True
        time.sleep(0.5)

    raise RuntimeError("O Ollama nao respondeu na API local. Verifique se a instalacao concluiu corretamente.")


def ollama_request(method, endpoint, *, payload=None, stream=False, timeout=(10, 300)):
    ensure_ollama_service(timeout=12)
    endpoint = endpoint if endpoint.startswith("/api/") else f"/api{endpoint}"
    response = requests.request(
        method=method,
        url=f"{OLLAMA_BASE_URL}{endpoint}",
        json=payload,
        stream=stream,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def list_local_ollama_models():
    response = ollama_request("GET", "/tags", timeout=(5, 20))
    data = response.json()
    models = {}
    for entry in data.get("models", []):
        name = entry.get("name") or entry.get("model")
        if name:
            models[name] = entry
    return models


def get_local_ollama_model_names():
    return set(list_local_ollama_models().keys())


def set_model_pull_state(model_id, **updates):
    state = llm_pull_status.get(model_id, {})
    state.update(updates)
    llm_pull_status[model_id] = state
    return state


def format_ollama_pull_progress(event):
    status = (event.get("status") or "").strip()
    completed = event.get("completed")
    total = event.get("total")
    if isinstance(completed, int) and isinstance(total, int) and total > 0:
        pct = max(0, min(100, int((completed / total) * 100)))
        return f"{status or 'Baixando modelo'} {pct}%"
    return status or "Preparando modelo..."


def explain_llm_failure(exc):
    details = str(exc).strip() or exc.__class__.__name__
    lowered = details.lower()

    hints = []
    if "connection refused" in lowered or "failed to establish a new connection" in lowered:
        hints.append("O Ollama nao respondeu na API local.")
        hints.append("O launcher agora tenta instalar e iniciar o Ollama automaticamente.")
    elif "read timed out" in lowered or "timed out" in lowered:
        hints.append("O Ollama demorou para responder. O modelo pode estar carregando ou baixando.")
    elif "not found" in lowered and ":" in details:
        hints.append("O modelo ainda nao existe localmente no Ollama.")
        hints.append("A interface pode baixar o modelo automaticamente.")
    elif "ollama nao foi encontrado" in lowered:
        hints.append(details)
        details = ""
    else:
        hints.append("Verifique se o Ollama esta instalado, iniciado e com acesso a GPU quando disponivel.")

    suffix = f" Detalhe tecnico: {details}" if details else ""
    return "Falha ao usar Ollama. " + " ".join(hints) + suffix


def pull_ollama_model(model_id):
    global llm_downloading, llm_last_error, llm_runtime_notice

    if model_id not in AVAILABLE_LLMS:
        raise ValueError(f"Modelo {model_id} nao encontrado.")

    model_info = AVAILABLE_LLMS[model_id]
    model_name = model_info["model"]
    set_model_pull_state(model_id, status="downloading", progress="Preparando download...", error=None)
    llm_downloading = True
    llm_last_error = None

    try:
        with ollama_request(
            "POST",
            "/pull",
            payload={"model": model_name, "stream": True},
            stream=True,
            timeout=(10, 1800),
        ) as response:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                event = json.loads(raw_line)
                if event.get("error"):
                    raise RuntimeError(event["error"])

                set_model_pull_state(
                    model_id,
                    status="downloading",
                    progress=format_ollama_pull_progress(event),
                    completed=event.get("completed"),
                    total=event.get("total"),
                    error=None,
                )

        set_model_pull_state(model_id, status="downloaded", progress="Modelo pronto.", error=None)
        llm_runtime_notice = f"{model_info['title']} pronto no Ollama."
        return True
    except Exception as exc:
        llm_last_error = explain_llm_failure(exc)
        set_model_pull_state(model_id, status="error", progress=None, error=llm_last_error)
        raise
    finally:
        llm_downloading = any(state.get("status") == "downloading" for state in llm_pull_status.values())


def start_model_pull(model_id):
    current_state = llm_pull_status.get(model_id, {})
    if current_state.get("status") == "downloading":
        return False

    def _worker():
        try:
            pull_ollama_model(model_id)
        except Exception:
            log.exception("Falha ao baixar modelo Ollama")

    threading.Thread(target=_worker, daemon=True).start()
    return True


def ensure_ollama_model(model_id, blocking=True):
    if model_id not in AVAILABLE_LLMS:
        raise ValueError(f"Modelo {model_id} nao encontrado.")

    model_name = AVAILABLE_LLMS[model_id]["model"]
    local_models = list_local_ollama_models()
    if model_name in local_models:
        set_model_pull_state(model_id, status="downloaded", progress="Modelo pronto.", error=None)
        return local_models[model_name]

    state = llm_pull_status.get(model_id, {})
    if state.get("status") == "downloading":
        if not blocking:
            return None
        deadline = time.time() + 1800
        while time.time() < deadline:
            local_models = list_local_ollama_models()
            if model_name in local_models:
                set_model_pull_state(model_id, status="downloaded", progress="Modelo pronto.", error=None)
                return local_models[model_name]
            state = llm_pull_status.get(model_id, {})
            if state.get("status") == "error":
                raise RuntimeError(state.get("error") or f"Falha ao baixar {model_name}.")
            time.sleep(1)
        raise RuntimeError(f"Tempo excedido aguardando o download de {model_name}.")

    if not blocking:
        start_model_pull(model_id)
        return None

    pull_ollama_model(model_id)
    return list_local_ollama_models().get(model_name)


def normalize_ollama_images(raw_images):
    normalized = []
    for item in raw_images or []:
        if not isinstance(item, str):
            continue
        payload = item.strip()
        if not payload:
            continue
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1].strip()
        if payload:
            normalized.append(payload)
    return normalized[:3]


class VisibleTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p", "div", "article", "section", "main", "li", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "br",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg", "footer", "nav", "form", "button"}

    def __init__(self):
        super().__init__()
        self.chunks = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = re.sub(r"\s+", " ", data or "").strip()
        if text:
            self.chunks.append(text)

    def get_text(self):
        return "".join(self.chunks)


def clean_html_fragment(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_extracted_text(text, max_chars=WEB_RESEARCH_FETCH_CHARS):
    lines = []
    seen = set()
    for raw_line in str(text or "").splitlines():
        line = unescape(raw_line).strip(" \t-•|")
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 30:
            continue
        lowered = line.lower()
        if lowered in seen:
            continue
        if lowered.startswith(("cookie", "aceitar", "privacy", "politica de privacidade")):
            continue
        seen.add(lowered)
        lines.append(line)
        if sum(len(item) + 1 for item in lines) >= max_chars:
            break

    joined = "\n".join(lines)
    return joined[:max_chars].strip()


def log_research_multiline(title, content):
    body = str(content or "").strip()
    if not body:
        body = "(vazio)"
    separator = "=" * 78
    log.info("%s\n[web-research] %s\n%s\n%s\n%s", separator, title, separator, body, separator)


def get_web_headers(referer=""):
    headers = dict(WEB_RESEARCH_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


def get_web_research_level(level):
    normalized = str(level or WEB_RESEARCH_DEFAULT_LEVEL).strip().lower()
    return normalized if normalized in WEB_RESEARCH_LEVELS else WEB_RESEARCH_DEFAULT_LEVEL


def get_web_research_settings(level):
    normalized = get_web_research_level(level)
    settings = dict(WEB_RESEARCH_LEVELS[normalized])
    settings["id"] = normalized
    return settings


def decode_search_result_url(url):
    raw = unescape(url or "").strip()
    if not raw:
        return ""
    if "duckduckgo.com/l/?" in raw:
        parsed = urlparse(raw)
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        raw = unquote(target or raw)
    return raw


def build_search_result(title, url, domain, *, snippet="", provider="", query="", prefetched_excerpt=""):
    return {
        "title": clean_html_fragment(title) or domain or url,
        "url": decode_search_result_url(url),
        "domain": str(domain or urlparse(decode_search_result_url(url)).netloc or "").strip(),
        "snippet": clean_html_fragment(snippet),
        "provider": str(provider or "").strip(),
        "query": str(query or "").strip(),
        "prefetched_excerpt": clean_extracted_text(prefetched_excerpt, max_chars=2000) if prefetched_excerpt else "",
    }


def extract_research_terms(text):
    folded = ascii_fold(sanitize_llm_text(text)).lower()
    tokens = re.findall(r"[a-z0-9]{3,}", folded)
    return [token for token in tokens if token not in RESEARCH_STOPWORDS]


def extract_core_research_terms(query):
    terms = extract_research_terms(query)
    core_terms = [term for term in terms if term not in RESEARCH_SOFT_TERMS]
    return core_terms or terms


def build_research_subject_profile(query):
    core_terms = extract_core_research_terms(query)
    ordered = []
    for term in core_terms:
        if term and term not in ordered:
            ordered.append(term)

    anchor_terms = [term for term in ordered if len(term) >= 4][:2]
    if not anchor_terms:
        anchor_terms = ordered[:2]

    phrase = " ".join(anchor_terms).strip()
    return {
        "core_terms": ordered,
        "anchor_terms": anchor_terms,
        "subject_label": phrase or sanitize_llm_text(query).strip(),
    }


def assess_source_relevance(query, source, excerpt=""):
    profile = build_research_subject_profile(query)
    title = ascii_fold(source.get("title", "")).lower()
    snippet = ascii_fold(source.get("snippet", "")).lower()
    url = ascii_fold(source.get("url", "")).lower()
    excerpt_sample = ascii_fold((excerpt or "")[:1800]).lower()
    haystack = " ".join(filter(None, [title, snippet, url, excerpt_sample])).strip()
    strong_haystack = " ".join(filter(None, [title, url])).strip()

    if not haystack:
        return {
            "score": 0,
            "matched_terms": [],
            "strong_matches": [],
            "anchor_terms": profile["anchor_terms"],
            "subject_label": profile["subject_label"],
            "is_relevant": False,
        }

    score = 0
    matched_terms = []
    strong_matches = []
    for term in profile["anchor_terms"]:
        if term in title:
            score += 5
            matched_terms.append(term)
            strong_matches.append(term)
        if term in url:
            score += 4
            matched_terms.append(term)
            strong_matches.append(term)
        if term in snippet:
            score += 2
            matched_terms.append(term)
        if excerpt_sample and term in excerpt_sample:
            score += 2
            matched_terms.append(term)

    matched_terms = sorted(set(matched_terms))
    strong_matches = sorted(set(strong_matches))

    required_matches = 2 if len(profile["anchor_terms"]) >= 2 else 1
    has_phrase = bool(profile["anchor_terms"]) and all(term in haystack for term in profile["anchor_terms"])
    has_strong_anchor = bool(strong_matches)
    is_relevant = len(matched_terms) >= required_matches and has_phrase and has_strong_anchor

    return {
        "score": score,
        "matched_terms": matched_terms,
        "strong_matches": strong_matches,
        "anchor_terms": profile["anchor_terms"],
        "subject_label": profile["subject_label"],
        "is_relevant": is_relevant,
    }


def score_search_result_relevance(query, result):
    relevance = assess_source_relevance(query, result)
    return {
        "score": relevance["score"],
        "matched_terms": relevance["matched_terms"],
        "strong_matches": relevance["strong_matches"],
        "anchor_terms": relevance["anchor_terms"],
        "subject_label": relevance["subject_label"],
        "is_relevant": relevance["is_relevant"],
    }


def extract_search_snippets(html_text, max_results=5):
    snippets = []
    patterns = [
        re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</', flags=re.I | re.S),
        re.compile(r'class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</', flags=re.I | re.S),
    ]

    for pattern in patterns:
        for match in pattern.finditer(html_text or ""):
            snippet = clean_html_fragment(match.group(1))
            if len(snippet) < 20:
                continue
            snippets.append(snippet)
            if len(snippets) >= max_results:
                return snippets
    return snippets


def extract_search_results(html_text, max_results=5):
    results = []
    seen = set()
    snippets = extract_search_snippets(html_text, max_results=max_results * 2)

    patterns = [
        re.compile(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.I | re.S,
        ),
        re.compile(
            r'<a[^>]+href="([^"]+)"[^>]+class="[^"]*(?:result-link|result__url|result__title)[^"]*"[^>]*>(.*?)</a>',
            flags=re.I | re.S,
        ),
        re.compile(
            r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.I | re.S,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(html_text or ""):
            url = decode_search_result_url(match.group(1))
            if not url.startswith(("http://", "https://")):
                continue
            parsed = urlparse(url)
            if not parsed.netloc or "duckduckgo.com" in parsed.netloc:
                continue
            if url in seen:
                continue

            title = clean_html_fragment(match.group(2)) or parsed.netloc
            if len(title) < 8:
                continue

            seen.add(url)
            results.append(build_search_result(
                title=title,
                url=url,
                domain=parsed.netloc,
                snippet=snippets[len(results)] if len(snippets) > len(results) else "",
                provider="duckduckgo_html",
            ))
            if len(results) >= max_results:
                return results
    return results


def iter_duckduckgo_related_topics(items):
    for item in items or []:
        if isinstance(item, dict) and item.get("Topics"):
            yield from iter_duckduckgo_related_topics(item.get("Topics"))
            continue
        if isinstance(item, dict):
            yield item


def search_duckduckgo_instant_results(query, max_results=5):
    response = requests.get(
        WEB_RESEARCH_DDG_INSTANT_URL,
        params={
            "q": query,
            "format": "json",
            "no_html": "1",
            "no_redirect": "1",
            "skip_disambig": "1",
            "t": "lyra-engine",
        },
        headers=get_web_headers("https://duckduckgo.com/"),
        timeout=(8, 20),
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    abstract_url = str(payload.get("AbstractURL") or "").strip()
    if abstract_url:
        parsed = urlparse(abstract_url)
        results.append(build_search_result(
            title=payload.get("Heading") or parsed.netloc,
            url=abstract_url,
            domain=parsed.netloc,
            snippet=payload.get("AbstractText") or "",
            provider="duckduckgo_instant",
            prefetched_excerpt=payload.get("AbstractText") or "",
        ))

    for topic in iter_duckduckgo_related_topics(payload.get("RelatedTopics")):
        first_url = str(topic.get("FirstURL") or "").strip()
        text = str(topic.get("Text") or "").strip()
        if not first_url or not text:
            continue
        parsed = urlparse(first_url)
        results.append(build_search_result(
            title=text.split(" - ", 1)[0][:180],
            url=first_url,
            domain=parsed.netloc,
            snippet=text,
            provider="duckduckgo_instant",
            prefetched_excerpt=text,
        ))
        if len(results) >= max_results:
            break

    return results[:max_results]


def search_duckduckgo_html_results(query, max_results=5):
    response = requests.get(
        WEB_RESEARCH_SEARCH_URL,
        params={"q": query},
        headers=get_web_headers("https://duckduckgo.com/"),
        timeout=(8, 25),
    )
    response.raise_for_status()
    return extract_search_results(response.text, max_results=max_results), response.status_code


def search_wikipedia_results(query, max_results=5, lang="pt"):
    endpoint = f"https://{lang}.wikipedia.org/w/api.php"
    response = requests.get(
        endpoint,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
            "utf8": "1",
        },
        headers=get_web_headers(f"https://{lang}.wikipedia.org/"),
        timeout=(8, 20),
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload.get("query", {}).get("search", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        page_path = quote(title.replace(" ", "_"), safe=":_()")
        page_url = f"https://{lang}.wikipedia.org/wiki/{page_path}"
        snippet = clean_html_fragment(item.get("snippet") or "")
        results.append(build_search_result(
            title=title,
            url=page_url,
            domain=f"{lang}.wikipedia.org",
            snippet=snippet,
            provider=f"wikipedia_{lang}",
            prefetched_excerpt=snippet,
        ))
    return results[:max_results]


def search_google_custom_results(query, max_results=5):
    if not WEB_RESEARCH_GOOGLE_API_KEY or not WEB_RESEARCH_GOOGLE_CSE_ID:
        return []

    response = requests.get(
        WEB_RESEARCH_GOOGLE_API_URL,
        params={
            "key": WEB_RESEARCH_GOOGLE_API_KEY,
            "cx": WEB_RESEARCH_GOOGLE_CSE_ID,
            "q": query,
            "num": min(max_results, 10),
            "hl": "pt-BR",
            "safe": "off",
        },
        headers=get_web_headers("https://www.google.com/"),
        timeout=(8, 20),
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload.get("items", []):
        link = str(item.get("link") or "").strip()
        if not link:
            continue
        parsed = urlparse(link)
        results.append(build_search_result(
            title=item.get("title") or parsed.netloc,
            url=link,
            domain=parsed.netloc,
            snippet=item.get("snippet") or "",
            provider="google_custom_search",
            prefetched_excerpt=item.get("snippet") or "",
        ))
    return results[:max_results]


def log_search_results(query, provider, results, status_hint="ok"):
    log.info(
        "[web-research] Provedor=%s query=%r status=%s resultados=%s",
        provider,
        query,
        status_hint,
        len(results),
    )
    for index, item in enumerate(results, start=1):
        log.info(
            "[web-research] Resultado #%s | provedor=%s | query=%r | titulo=%r | domain=%s | url=%s",
            index,
            provider,
            query,
            item.get("title", ""),
            item.get("domain", ""),
            item.get("url", ""),
        )
        if item.get("snippet"):
            log_research_multiline(
                f"Snippet do buscador #{index} | {provider} | {item.get('domain', '')}",
                item.get("snippet", ""),
            )


def fetch_search_results(query, max_results=5):
    log.info("[web-research] Pesquisando query=%r max_results=%s", query, max_results)

    providers = []
    if WEB_RESEARCH_GOOGLE_API_KEY and WEB_RESEARCH_GOOGLE_CSE_ID:
        providers.append(("google_custom_search", search_google_custom_results))
    providers.extend([
        ("duckduckgo_instant", search_duckduckgo_instant_results),
        ("duckduckgo_html", lambda q, limit: search_duckduckgo_html_results(q, limit)[0]),
        ("wikipedia_pt", lambda q, limit: search_wikipedia_results(q, limit, lang="pt")),
        ("wikipedia_en", lambda q, limit: search_wikipedia_results(q, limit, lang="en")),
    ])

    provider_priority = {
        "google_custom_search": 0,
        "duckduckgo_html": 1,
        "duckduckgo_instant": 2,
        "wikipedia_pt": 3,
        "wikipedia_en": 4,
    }

    aggregated = []
    seen_urls = set()

    for provider_name, provider_fn in providers:
        try:
            provider_results = provider_fn(query, max_results)
            log_search_results(query, provider_name, provider_results, status_hint="ok")
        except Exception as exc:
            log.warning("[web-research] Provedor=%s query=%r falhou: %s", provider_name, query, exc)
            continue

        for item in provider_results:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            item["query"] = query
            aggregated.append(item)

    ranked = []
    for item in aggregated:
        relevance = score_search_result_relevance(query, item)
        item["_relevance_score"] = relevance["score"]
        item["_matched_terms"] = relevance["matched_terms"]
        if not relevance["is_relevant"]:
            log.info(
                "[web-research] Ignorando resultado pouco relevante | query=%r | titulo=%r | matched=%s | strong=%s | anchors=%s | score=%s",
                query,
                item.get("title", ""),
                relevance["matched_terms"],
                relevance.get("strong_matches", []),
                relevance.get("anchor_terms", []),
                relevance["score"],
            )
            continue
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            -int(item.get("_relevance_score", 0)),
            provider_priority.get(item.get("provider", ""), 99),
            len(item.get("title", "")),
        )
    )
    return ranked[:max_results]


def fetch_page_excerpt(url, max_chars=WEB_RESEARCH_FETCH_CHARS):
    log.info("[web-research] Lendo pagina url=%s", url)
    response = requests.get(url, headers=get_web_headers("https://www.google.com/"), timeout=(8, 20))
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding or "utf-8"
    content_type = str(response.headers.get("content-type", "")).lower()
    log.info(
        "[web-research] Resposta pagina url=%s status=%s content_type=%s final_url=%s",
        url,
        response.status_code,
        content_type,
        response.url,
    )
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type and "text/plain" not in content_type:
        raise RuntimeError("Tipo de conteudo nao suportado para leitura textual.")

    raw_text = response.text
    if "text/html" in content_type or "xhtml" in content_type:
        raw_text = re.sub(r"<!--.*?-->", " ", raw_text, flags=re.S)
        extractor = VisibleTextExtractor()
        extractor.feed(raw_text)
        raw_text = extractor.get_text()

    cleaned_for_log = clean_extracted_text(raw_text, max_chars=max(max_chars, 25000))
    cleaned = cleaned_for_log[:max_chars].strip()
    log_research_multiline(f"Texto extraido | {url}", cleaned_for_log or "(sem texto util)")
    if len(cleaned) < 120:
        raise RuntimeError("Pouco texto util encontrado na pagina.")
    return cleaned


def fetch_special_source_excerpt(source, max_chars=WEB_RESEARCH_FETCH_CHARS):
    url = str(source.get("url") or "").strip()
    domain = str(source.get("domain") or "").strip().lower()
    if not url or "wikipedia.org" not in domain:
        return ""

    parsed = urlparse(url)
    slug = parsed.path.split("/wiki/", 1)[1] if "/wiki/" in parsed.path else ""
    slug = slug.strip("/")
    if not slug:
        return ""

    summary_url = f"{parsed.scheme}://{parsed.netloc}/api/rest_v1/page/summary/{slug}"
    log.info("[web-research] Lendo resumo oficial da Wikipedia url=%s", summary_url)
    response = requests.get(
        summary_url,
        headers=get_web_headers(f"{parsed.scheme}://{parsed.netloc}/"),
        timeout=(8, 20),
    )
    response.raise_for_status()
    payload = response.json()
    text = "\n".join(
        part for part in [
            payload.get("title"),
            payload.get("description"),
            payload.get("extract"),
        ] if part
    )
    cleaned = clean_extracted_text(text, max_chars=max_chars)
    log_research_multiline(f"Texto extraido via Wikipedia API | {url}", cleaned or "(sem texto util)")
    return cleaned


def extract_search_queries(text, max_queries=3):
    queries = []
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", raw_line).strip().strip('"')
        line = re.sub(r"\s+", " ", line)
        if len(line) < 8:
            continue
        if line.lower() in {item.lower() for item in queries}:
            continue
        queries.append(line)
        if len(queries) >= max_queries:
            break
    return queries


def extract_user_text_messages(messages, limit=4):
    items = []
    for msg in reversed(messages or []):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = sanitize_llm_text(msg.get("content", "")).strip()
        if not content:
            continue
        content = re.sub(r"\s+", " ", content).strip()
        items.append(content[:260])
        if len(items) >= limit:
            break
    return list(reversed(items))


def is_ambiguous_research_prompt(text):
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if len(cleaned) < 20:
        return True
    pronouns = [
        "ele", "ela", "isso", "isto", "aquilo", "essa", "esse", "essa pesquisa",
        "o que ela", "o que ele", "e ai", "e isso", "resultado disso",
    ]
    return any(token in cleaned for token in pronouns)


def build_research_subject(messages, user_question):
    current = re.sub(r"\s+", " ", sanitize_llm_text(user_question)).strip()
    recent_users = extract_user_text_messages(messages, limit=4)
    recent_without_current = [item for item in recent_users if item != current]

    if not is_ambiguous_research_prompt(current):
        return current, recent_users

    if recent_without_current:
        subject = f"{recent_without_current[-1]} | complemento: {current}"
        return subject, recent_users

    return current, recent_users


def looks_like_music_creation_request(text):
    folded = ascii_fold(sanitize_llm_text(text)).lower()
    folded = re.sub(r"\s+", " ", folded).strip()
    return any(marker in folded for marker in MUSIC_CREATION_MARKERS)


def normalize_search_query_text(text):
    cleaned = sanitize_llm_text(text).replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def cleanup_search_phrase_fragment(fragment, max_terms=5):
    if not fragment:
        return ""
    tokens = re.findall(r"[a-z0-9]{2,}", ascii_fold(fragment).lower())
    cleaned = []
    for token in tokens:
        if token in RESEARCH_STOPWORDS or token in RESEARCH_SOFT_TERMS or token in CREATIVE_SEARCH_NOISE_TERMS:
            continue
        if token in cleaned:
            continue
        cleaned.append(token)
        if len(cleaned) >= max_terms:
            break
    return " ".join(cleaned).strip()


def build_creative_music_search_profile(text, desired_count=4):
    if not looks_like_music_creation_request(text):
        return None

    cleaned = normalize_search_query_text(text)
    folded = ascii_fold(cleaned).lower()
    style_phrase = ""
    theme_phrase = ""

    style_patterns = [
        r"\b(?:estilo|sonoridade|pegada|genero|g[eê]nero|ritmo|ritimo)\s+(?:de\s+)?([a-z0-9\s/\-]{3,90})",
        r"\b(?:inspirado em|inspirada em|referencia de|referencias de)\s+([a-z0-9\s/\-]{3,90})",
    ]
    for pattern in style_patterns:
        match = re.search(pattern, folded)
        if match:
            style_phrase = cleanup_search_phrase_fragment(match.group(1), max_terms=5)
            if style_phrase:
                break

    theme_patterns = [
        r"\bsobre\s+([a-z0-9\s/\-]{3,90})",
        r"\btema\s+(?:principal\s+)?([a-z0-9\s/\-]{3,90})",
        r"\bassunto\s+([a-z0-9\s/\-]{3,90})",
    ]
    for pattern in theme_patterns:
        match = re.search(pattern, folded)
        if match:
            theme_phrase = cleanup_search_phrase_fragment(match.group(1), max_terms=4)
            if theme_phrase:
                break

    remaining_terms = []
    for term in extract_core_research_terms(cleaned):
        if term in CREATIVE_SEARCH_NOISE_TERMS:
            continue
        if term not in remaining_terms:
            remaining_terms.append(term)

    if not style_phrase:
        style_terms = [term for term in remaining_terms if term in MUSIC_STYLE_HINT_TERMS][:4]
        style_phrase = " ".join(style_terms).strip()
    else:
        style_terms = [term for term in style_phrase.split() if term]

    if not theme_phrase:
        theme_terms = [term for term in remaining_terms if term not in style_terms][:4]
        theme_phrase = " ".join(theme_terms).strip()
    else:
        theme_terms = [term for term in theme_phrase.split() if term]

    label_parts = []
    for term in [*style_terms, *theme_terms]:
        if term and term not in label_parts:
            label_parts.append(term)
    label = " ".join(label_parts[:6]).strip() or cleanup_search_phrase_fragment(cleaned, max_terms=6)
    if not label:
        return None

    queries = []
    seen = set()

    def add_query(value):
        candidate = normalize_search_query_text(value)
        lowered = ascii_fold(candidate).lower()
        if len(candidate) < 8 or lowered in seen:
            return
        seen.add(lowered)
        queries.append(candidate)

    if style_phrase and theme_phrase:
        add_query(f"melhores musicas {style_phrase} sobre {theme_phrase}")
        add_query(f"refroes {style_phrase} com tema {theme_phrase}")
        add_query(f"arranjos {style_phrase} instrumentacao producao")
        add_query(f"referencias vocais {style_phrase} letras tema {theme_phrase}")
    elif style_phrase:
        add_query(f"melhores musicas {style_phrase}")
        add_query(f"refroes marcantes {style_phrase}")
        add_query(f"arranjos {style_phrase} instrumentacao producao")
        add_query(f"referencias vocais {style_phrase}")
    elif theme_phrase:
        add_query(f"musicas sobre {theme_phrase}")
        add_query(f"refroes sobre {theme_phrase}")
        add_query(f"letras e temas sobre {theme_phrase}")
        add_query(f"arranjos para musica sobre {theme_phrase}")

    add_query(label)
    return {
        "label": label,
        "style_phrase": style_phrase,
        "theme_phrase": theme_phrase,
        "queries": queries[:desired_count],
    }


def build_explicit_research_profile(text, desired_count=4):
    cleaned = normalize_search_query_text(text)
    folded = ascii_fold(cleaned).lower()
    if len(cleaned) < 8:
        return None

    subject_phrase = ""
    subject_patterns = [
        r"\b(?:ritm(?:o|os|i?mo|i?mos)|estilo(?: musical)?|influencias(?: musicais)?|musicas|letras|discografia|biografia|entrevista|arranjos?|tom|sonoridade)\s+(?:do|da|dos|das|de)\s+([a-z0-9\s/&\-]{3,80})",
        r"\bsobre\s+([a-z0-9\s/&\-]{3,80})",
    ]
    for pattern in subject_patterns:
        match = re.search(pattern, folded)
        if not match:
            continue
        subject_phrase = cleanup_search_phrase_fragment(match.group(1), max_terms=5)
        if subject_phrase:
            break

    if not subject_phrase:
        profile = build_research_subject_profile(cleaned)
        subject_phrase = cleanup_search_phrase_fragment(profile.get("subject_label", ""), max_terms=5)

    if not subject_phrase:
        return None

    requested_suffixes = []

    def add_suffix(value):
        suffix = normalize_search_query_text(value)
        if suffix and suffix not in requested_suffixes:
            requested_suffixes.append(suffix)

    if re.search(r"\britm(?:o|os|i?mo|i?mos)\b", folded) or any(term in folded for term in ["estilo", "sonoridade", "arranjo", "arranjos", "tom"]):
        add_suffix("estilo musical")
        add_suffix("influencias musicais")
        add_suffix("arranjos e producao")
    if "musica" in folded or "musicas" in folded:
        add_suffix("musicas")
    if "letra" in folded or "letras" in folded:
        add_suffix("letras")
    if "biografia" in folded:
        add_suffix("biografia")
    if "discografia" in folded:
        add_suffix("discografia")
    if "entrevista" in folded:
        add_suffix("entrevista")

    if not requested_suffixes:
        add_suffix("estilo musical")
        add_suffix("influencias musicais")
        add_suffix("musicas")
        add_suffix("letras")

    queries = []
    seen = set()

    def add_query(value):
        candidate = normalize_search_query_text(value)
        lowered = ascii_fold(candidate).lower()
        if len(candidate) < 6 or lowered in seen:
            return
        seen.add(lowered)
        queries.append(candidate)

    add_query(subject_phrase)
    for suffix in requested_suffixes:
        add_query(f"{subject_phrase} {suffix}")

    return {
        "label": subject_phrase,
        "queries": queries[:desired_count],
        "requested_suffixes": requested_suffixes[:desired_count],
    }


def build_seed_research_queries(messages, user_question, desired_count):
    subject, recent_users = build_research_subject(messages, user_question)
    current_clean = re.sub(r"\s+", " ", sanitize_llm_text(user_question)).strip()[:180]
    base_subject = re.sub(r"\s+", " ", subject).strip()[:180]
    prior_subject = re.sub(r"\s+", " ", recent_users[-2]).strip()[:180] if len(recent_users) >= 2 else base_subject
    primary_subject = prior_subject if is_ambiguous_research_prompt(current_clean) else base_subject

    seeds = []
    seen = set()

    def add_query(value):
        candidate = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(candidate) < 8:
            return
        lowered = candidate.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        seeds.append(candidate)

    explicit_profile = build_explicit_research_profile(primary_subject, desired_count=max(desired_count, 4))
    if explicit_profile:
        for query in explicit_profile["queries"]:
            add_query(query)
        return seeds[:desired_count], explicit_profile["label"], recent_users

    creative_profile = build_creative_music_search_profile(primary_subject, desired_count=max(desired_count, 4))
    if creative_profile:
        for query in creative_profile["queries"]:
            add_query(query)
        if len(seeds) < desired_count:
            add_query(creative_profile["label"])
        return seeds[:desired_count], creative_profile["label"], recent_users

    add_query(primary_subject)
    if current_clean and current_clean != primary_subject:
        add_query(f"{primary_subject} {current_clean}")
    add_query(base_subject)

    suffixes = [
        "biografia",
        "estilo musical",
        "influencias musicais",
        "entrevista",
        "discografia",
        "producao musical",
        "voz e tecnica vocal",
        "letras e temas",
    ]
    for suffix in suffixes:
        if len(seeds) >= desired_count:
            break
        add_query(f"{primary_subject} {suffix}")

    return seeds[:desired_count], primary_subject, recent_users


def expand_research_queries(user_question, planned_queries, desired_count):
    queries = []
    seen = set()

    def add_query(value):
        candidate = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(candidate) < 8:
            return
        lowered = candidate.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        queries.append(candidate)

    creative_profile = build_creative_music_search_profile(user_question, desired_count=max(desired_count, 4))
    if creative_profile:
        for query in creative_profile["queries"]:
            add_query(query)
        base_question = creative_profile["label"]
    else:
        base_question = normalize_search_query_text(user_question)[:180]

    for query in planned_queries or []:
        add_query(query)

    add_query(base_question)

    suffixes = [
        "estilo musical",
        "influencias musicais",
        "entrevista",
        "analise",
        "producao musical",
        "instrumentacao",
        "voz e tecnica vocal",
        "letras e temas",
    ]
    for suffix in suffixes:
        if len(queries) >= desired_count:
            break
        add_query(f"{base_question} {suffix}")

    return queries[:desired_count]


def plan_research_queries(llm, messages, user_question, temperature, repeat_penalty, desired_count=3):
    seed_queries, subject_context, recent_users = build_seed_research_queries(messages, user_question, desired_count)
    log.info("[web-research] Assunto base=%r | mensagens_recentes=%s", subject_context, recent_users[-3:])
    log.info("[web-research] Queries seed=%s", seed_queries)
    creative_profile = build_creative_music_search_profile(user_question, desired_count=max(desired_count, 4))
    if creative_profile and len(seed_queries) >= desired_count:
        log.info("[web-research] Planner pulado: usando queries deterministicas para pedido criativo.")
        log.info("[web-research] Queries planejadas finais=%s", seed_queries[:desired_count])
        return seed_queries[:desired_count]
    planner_messages = [
        {
            "role": "system",
            "content": (
                "Voce cria buscas web curtas e objetivas para pesquisa musical factual. "
                f"Responda com {max(2, desired_count - 1)} a {desired_count} linhas, "
                "uma consulta por linha, sem numeracao, sem comentarios. "
                "Se o pedido vier em formato de pedido criativo, converta-o em consultas naturais que um mecanismo de busca realmente entenderia. "
                "Nunca pesquise frases como 'ajude-me', 'me ajuda', 'quero que voce crie' ou pedidos completos de composicao. "
                "Transforme pedidos criativos em buscas sobre referencias reais, artistas, musicas, refrões, arranjos, instrumentacao, producao e tecnicas. "
                "Nunca troque o assunto principal da conversa por outro artista ou banda. "
                "Nunca adicione nomes de pessoas, bandas ou premios que nao estejam no assunto confirmado. "
                "Se a pergunta for sobre identidade, biografia ou significado, mantenha as consultas literais e conservadoras. "
                "Exemplo ruim: Ajude-me a compor um refrao pop animado sobre o verao. "
                "Exemplo bom: melhores musicas pop animadas de verao."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Pedido atual do usuario: {user_question}\n"
                f"Assunto principal confirmado: {subject_context}\n"
                f"Ultimas mensagens do usuario: {' | '.join(recent_users[-3:])}\n"
                f"Consultas base ja previstas: {' | '.join(seed_queries)}\n"
                "Crie consultas para pesquisar estilo musical, referencias, tecnicas, bandas, voz, producao, entrevistas, letras ou contexto, mantendo exatamente esse assunto. "
                "Se o pedido for criativo, reescreva em termos pesquisaveis de buscador."
            ),
        },
    ]
    try:
        planned = run_llm_completion(
            llm,
            messages=planner_messages,
            max_tokens=96,
            temperature=min(temperature, 0.05),
            repeat_penalty=repeat_penalty,
            finalizer=sanitize_llm_text,
            keep_alive=resolve_ollama_keep_alive(),
        )
        queries = extract_search_queries(planned, max_queries=desired_count)
    except Exception:
        queries = []

    merged = expand_research_queries(subject_context, [*seed_queries, *queries], desired_count)
    log.info("[web-research] Queries planejadas finais=%s", merged[:desired_count])
    return merged[:desired_count]


def build_research_excerpt_preview(excerpt, max_chars=340):
    preview = re.sub(r"\s+", " ", str(excerpt or "")).strip()
    if len(preview) <= max_chars:
        return preview
    return preview[: max_chars - 3].rstrip() + "..."


def build_research_summary_messages(user_question, source, excerpt):
    subject_profile = build_research_subject_profile(user_question)
    anchor_terms = ", ".join(subject_profile["anchor_terms"]) or subject_profile["subject_label"]
    return [
        {
            "role": "system",
            "content": (
                "Voce verifica e resume uma unica fonte web para pesquisa musical factual. "
                "Use apenas fatos explicitamente presentes no texto extraido. "
                "Nunca invente ligacoes entre artistas, albuns, premios, pessoas ou bandas. "
                "Nunca troque o assunto principal por outra pessoa, banda, premio, pagina generica ou colaborador citado na pagina. "
                "Se a fonte nao for claramente sobre o assunto pedido, ou se citar o assunto apenas de passagem, "
                "responda exatamente com a palavra IRRELEVANTE. "
                "Se a fonte for relevante, responda em Portugues do Brasil com 2 a 4 bullets curtos, sem introducao, "
                "sem frases como 'aqui esta um resumo', e sem copiar letras completas."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Pedido do usuario: {user_question}\n"
                f"Assunto principal a confirmar: {subject_profile['subject_label']}\n"
                f"Termos-ancora obrigatorios: {anchor_terms}\n"
                f"Consulta usada para achar a fonte: {source.get('query')}\n"
                f"Fonte: {source.get('title')} ({source.get('url')})\n"
                f"Texto extraido:\n{excerpt}"
            ),
        },
    ]


def summarize_research_source(llm, user_question, source, excerpt, temperature, repeat_penalty):
    relevance = assess_source_relevance(user_question, source, excerpt)
    if not relevance["is_relevant"]:
        log.info(
            "[web-research] Fonte descartada antes do resumo | titulo=%r | matched=%s | strong=%s | anchors=%s | score=%s",
            source.get("title", ""),
            relevance["matched_terms"],
            relevance.get("strong_matches", []),
            relevance.get("anchor_terms", []),
            relevance["score"],
        )
        return ""

    summary_messages = build_research_summary_messages(user_question, source, excerpt)
    summary = run_llm_completion(
        llm,
        messages=summary_messages,
        max_tokens=220,
        temperature=min(temperature, 0.08),
        repeat_penalty=repeat_penalty,
        finalizer=sanitize_llm_text,
        keep_alive=resolve_ollama_keep_alive(),
    ).strip()
    if ascii_fold(summary).strip().lower().startswith("irrelevante"):
        return ""
    return summary


def format_research_context(user_question, research_items):
    lines = [
        "Resultado da pesquisa:",
        f"Pedido original do usuario: {user_question}",
        "Use apenas os fatos confirmados abaixo quando a pergunta depender da web.",
        "Se usar fatos das fontes, cite inline como [1], [2], [3].",
    ]
    for index, item in enumerate(research_items, start=1):
        lines.extend([
            f"[{index}] {item.get('title')} | {item.get('domain')}",
            f"URL: {item.get('url')}",
            f"Consulta: {item.get('query')}",
            f"Resumo: {item.get('summary')}",
        ])
    return "\n".join(lines)


def build_empty_research_context(user_question):
    return (
        "Resultado da pesquisa:\n"
        f"Pedido original do usuario: {user_question}\n"
        "Nenhuma fonte valida foi extraida da web. "
        "Nao invente fatos externos; diga claramente que a pesquisa nao trouxe resultados confiaveis."
    )


def strip_wrapping_quotes(text):
    value = str(text or "").strip()
    quote_pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
    for left, right in quote_pairs:
        if value.startswith(left) and value.endswith(right) and len(value) >= 2:
            return value[1:-1].strip()
    return value


def normalize_style_block_lines(text):
    cleaned = sanitize_llm_text(strip_markdown_code_fence(text)).replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines = []
    seen = set()
    label_hints = {
        "clima", "genero", "gênero", "arranjo", "instrumentacao", "instrumentação",
        "referencias", "referências", "voz", "vocal", "bpm", "groove",
    }

    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line)
        line = re.sub(r"[*_`]+", "", line).strip()
        if not line:
            continue
        if ":" in line:
            left, right = line.split(":", 1)
            if ascii_fold(left).lower().strip() in label_hints and right.strip():
                line = right.strip()
        if line.startswith("[") and line.endswith("]"):
            normalized = line
        else:
            normalized = f"[{line.strip('[] ')}]"
        dedupe_key = ascii_fold(normalized).lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_lines.append(normalized)

    return "\n".join(normalized_lines).strip()


def normalize_quoted_lyric_lines(text):
    cleaned = sanitize_llm_text(strip_markdown_code_fence(text)).replace("\r\n", "\n").replace("\r", "\n")
    lines = []

    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        heading_candidate = strip_wrapping_quotes(line)
        heading_candidate = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", heading_candidate).strip()
        if heading_candidate.startswith("(") and heading_candidate.endswith(")"):
            heading_candidate = heading_candidate[1:-1].strip()

        normalized_tag = normalize_section_tag(heading_candidate)
        if normalized_tag and (
            line.startswith("[")
            or re.match(r"^(?:intro|verse|verso|estrofe|pre-chorus|pre chorus|chorus|refrao|refr[aã]o|bridge|ponte|hook|outro|final chorus)\b", ascii_fold(heading_candidate).lower())
        ):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(normalized_tag)
            continue

        if line.startswith("[") and line.endswith("]"):
            lines.append(line)
            continue

        lyric_line = strip_wrapping_quotes(line)
        lyric_line = re.sub(r"[*_`]+", "", lyric_line).strip()
        if not lyric_line:
            continue
        lines.append(f"\"{lyric_line}\"")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()


def normalize_music_chat_reply(text):
    cleaned = sanitize_llm_text(text).strip()
    if not cleaned:
        return ""

    block_pattern = re.compile(r"```([^\n`]*)\n([\s\S]*?)```")

    def replace_block(match):
        raw_label = (match.group(1) or "").strip()
        label = ascii_fold(raw_label).lower().strip()
        body = (match.group(2) or "").strip()
        if not body:
            return match.group(0)

        if label in {"style", "estilo", "ritmo", "ritimo", "caption", "arranjo", "arrangement"}:
            body = normalize_style_block_lines(body) or body
        elif label in {"lyrics", "letra", "letras"}:
            body = normalize_quoted_lyric_lines(body) or body

        return f"```{raw_label}\n{body}\n```"

    return block_pattern.sub(replace_block, cleaned)


def detect_chat_response_mode(messages, user_question, web_search_enabled=False, research_context=""):
    text = ascii_fold(sanitize_llm_text(user_question)).lower()
    text = re.sub(r"\s+", " ", text).strip()

    music_creation_markers = [
        "cria uma musica", "criar uma musica", "compoe", "compor", "compõe",
        "escreve uma letra", "escrever uma letra", "gera uma letra", "gerar uma letra",
        "faz uma musica", "faça uma musica", "faca uma musica", "transforma em musica",
        "transforme em musica", "me da uma letra", "me de uma letra", "refrao", "refrão",
        "verso", "pre-chorus", "chorus", "bridge", "arranjo", "arrangement", "bpm",
        "style", "lyrics", "title", "duration", "exporta", "exportar para criar",
        "briefing musical", "prompt musical",
    ]
    informational_markers = [
        "quem e", "quem foi", "o que e", "o que foi", "qual e", "quais sao",
        "como e", "como foi", "quando", "onde", "por que", "porque",
        "pesquisa", "pesquise", "procura", "procure", "resuma", "resumir",
        "explica", "explique", "me diga", "fale sobre", "fala sobre",
        "me conta", "biografia", "discografia", "entrevista",
    ]

    has_music_intent = any(marker in text for marker in MUSIC_CREATION_MARKERS)
    has_info_intent = any(marker in text for marker in INFORMATIONAL_MARKERS)

    if has_music_intent:
        return "music"

    if web_search_enabled and research_context:
        return "informational"

    if has_info_intent:
        return "informational"

    recent_user_messages = extract_user_text_messages(messages, limit=3)
    recent_blob = " | ".join(ascii_fold(item).lower() for item in recent_user_messages)
    if any(marker in recent_blob for marker in MUSIC_CREATION_MARKERS):
        return "music"

    return "informational" if any(ch in text for ch in ["?", "quem", "qual", "como"]) else "music"


def should_run_web_research(user_question, response_mode, requested_enabled=False):
    if not requested_enabled:
        return False

    text = ascii_fold(sanitize_llm_text(user_question)).lower()
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return False

    if response_mode == "informational":
        return True

    return any(marker in text for marker in EXPLICIT_WEB_RESEARCH_MARKERS)


def run_web_research(
    llm,
    messages,
    user_question,
    temperature,
    repeat_penalty,
    search_level=WEB_RESEARCH_DEFAULT_LEVEL,
    progress_callback=None,
):
    progress_callback = progress_callback or (lambda payload: None)
    settings = get_web_research_settings(search_level)
    log.info(
        "[web-research] Iniciando pesquisa nivel=%s sites=%s queries=%s resultados_por_query=%s pergunta=%r",
        settings["id"],
        settings["max_sites"],
        settings["query_count"],
        settings["results_per_query"],
        user_question,
    )

    progress_callback({
        "type": "research_status",
        "status": "planning",
        "message": f"Planejando buscas ({settings['title']} · {settings['max_sites']} sites)...",
    })
    queries = plan_research_queries(
        llm,
        messages,
        user_question,
        temperature,
        repeat_penalty,
        desired_count=settings["query_count"],
    )
    progress_callback({
        "type": "research_queries",
        "queries": queries,
        "level": settings["id"],
        "max_sites": settings["max_sites"],
    })

    all_results = []
    seen_urls = set()
    for query in queries:
        progress_callback({
            "type": "research_status",
            "status": "searching",
            "message": f"Pesquisando: {query}",
            "query": query,
        })
        try:
            results = fetch_search_results(query, max_results=settings["results_per_query"])
        except Exception as exc:
            progress_callback({
                "type": "research_status",
                "status": "warning",
                "message": f"Falha ao pesquisar '{query}': {exc}",
                "query": query,
            })
            continue

        for result in results:
            if result["url"] in seen_urls:
                continue
            seen_urls.add(result["url"])
            result["query"] = query
            all_results.append(result)
            progress_callback({"type": "research_source", "source": {**result, "status": "discovered"}})
            if len(all_results) >= settings["max_sites"]:
                break
        if len(all_results) >= settings["max_sites"]:
            break

    research_items = []
    for index, source in enumerate(all_results, start=1):
        source_id = f"source_{index}"
        progress_callback({"type": "research_source", "source": {**source, "id": source_id, "status": "fetching"}})
        try:
            excerpt = fetch_special_source_excerpt(source) or fetch_page_excerpt(source["url"])
        except Exception as exc:
            excerpt = clean_extracted_text(
                "\n".join(filter(None, [source.get("prefetched_excerpt", ""), source.get("snippet", "")])),
                max_chars=800,
            )
            if len(excerpt) < 60:
                log.warning("[web-research] Falha ao ler url=%s erro=%s", source.get("url", ""), exc)
                progress_callback({
                    "type": "research_source",
                    "source": {**source, "id": source_id, "status": "error", "summary": f"Falha ao ler: {exc}"},
                })
                continue
            log.warning(
                "[web-research] Usando snippet do buscador como fallback url=%s erro=%s",
                source.get("url", ""),
                exc,
            )
            log_research_multiline(f"Texto fallback por snippet | {source.get('url', '')}", excerpt)

        excerpt_preview = build_research_excerpt_preview(excerpt)
        relevance = assess_source_relevance(user_question, source, excerpt)
        if not relevance["is_relevant"]:
            progress_callback({
                "type": "research_source",
                "source": {
                    **source,
                    "id": source_id,
                    "status": "error",
                    "excerpt_preview": excerpt_preview,
                    "summary": "Fonte descartada por nao confirmar o assunto principal.",
                },
            })
            continue

        progress_callback({
            "type": "research_source",
            "source": {
                **source,
                "id": source_id,
                "status": "summarizing",
                "excerpt_preview": excerpt_preview,
                "summary": "Resumindo a fonte...",
            },
        })
        try:
            summary = summarize_research_source(
                llm,
                user_question=user_question,
                source=source,
                excerpt=excerpt,
                temperature=temperature,
                repeat_penalty=repeat_penalty,
            )
        except Exception as exc:
            progress_callback({
                "type": "research_source",
                "source": {**source, "id": source_id, "status": "error", "summary": f"Falha ao resumir: {exc}"},
            })
            continue

        if not summary:
            progress_callback({
                "type": "research_source",
                "source": {**source, "id": source_id, "status": "error", "summary": "Fonte ignorada por baixa relevancia."},
            })
            continue

        item = {
            "id": source_id,
            "title": source["title"],
            "url": source["url"],
            "domain": source["domain"],
            "query": source.get("query", ""),
            "excerpt_preview": excerpt_preview,
            "summary": summary,
            "status": "ready",
        }
        research_items.append(item)
        log_research_multiline(f"Resumo da fonte | {item['domain']}", item["summary"])
        progress_callback({"type": "research_source", "source": item})

    if research_items:
        progress_callback({
            "type": "research_status",
            "status": "ready",
            "message": f"{len(research_items)} fonte(s) resumida(s).",
        })
        return {
            "items": research_items,
            "context": format_research_context(user_question, research_items),
        }

    progress_callback({
        "type": "research_status",
        "status": "warning",
        "message": "Nao encontrei fontes uteis na web para esse pedido.",
    })
    return {"items": [], "context": build_empty_research_context(user_question)}


def stream_web_research(
    llm,
    messages,
    user_question,
    temperature,
    repeat_penalty,
    search_level=WEB_RESEARCH_DEFAULT_LEVEL,
):
    settings = get_web_research_settings(search_level)
    log.info(
        "[web-research] Iniciando pesquisa stream nivel=%s sites=%s queries=%s resultados_por_query=%s pergunta=%r",
        settings["id"],
        settings["max_sites"],
        settings["query_count"],
        settings["results_per_query"],
        user_question,
    )
    queries = []
    research_items = []
    all_results = []
    seen_urls = set()

    yield {
        "type": "research_status",
        "status": "planning",
        "message": f"Planejando buscas ({settings['title']} · {settings['max_sites']} sites)...",
    }
    queries = plan_research_queries(
        llm,
        messages,
        user_question,
        temperature,
        repeat_penalty,
        desired_count=settings["query_count"],
    )
    yield {
        "type": "research_queries",
        "queries": queries,
        "level": settings["id"],
        "max_sites": settings["max_sites"],
    }

    for query in queries:
        yield {
            "type": "research_status",
            "status": "searching",
            "message": f"Pesquisando: {query}",
            "query": query,
        }
        try:
            results = fetch_search_results(query, max_results=settings["results_per_query"])
        except Exception as exc:
            yield {
                "type": "research_status",
                "status": "warning",
                "message": f"Falha ao pesquisar '{query}': {exc}",
                "query": query,
            }
            continue

        for result in results:
            if result["url"] in seen_urls:
                continue
            seen_urls.add(result["url"])
            result["query"] = query
            all_results.append(result)
            yield {"type": "research_source", "source": {**result, "status": "discovered"}}
            if len(all_results) >= settings["max_sites"]:
                break
        if len(all_results) >= settings["max_sites"]:
            break

    for index, source in enumerate(all_results, start=1):
        source_id = f"source_{index}"
        yield {"type": "research_source", "source": {**source, "id": source_id, "status": "fetching"}}
        try:
            excerpt = fetch_special_source_excerpt(source) or fetch_page_excerpt(source["url"])
        except Exception as exc:
            excerpt = clean_extracted_text(
                "\n".join(filter(None, [source.get("prefetched_excerpt", ""), source.get("snippet", "")])),
                max_chars=800,
            )
            if len(excerpt) < 60:
                log.warning("[web-research] Falha ao ler url=%s erro=%s", source.get("url", ""), exc)
                yield {
                    "type": "research_source",
                    "source": {**source, "id": source_id, "status": "error", "summary": f"Falha ao ler: {exc}"},
                }
                continue
            log.warning(
                "[web-research] Usando snippet do buscador como fallback url=%s erro=%s",
                source.get("url", ""),
                exc,
            )
            log_research_multiline(f"Texto fallback por snippet | {source.get('url', '')}", excerpt)

        excerpt_preview = build_research_excerpt_preview(excerpt)
        relevance = assess_source_relevance(user_question, source, excerpt)
        if not relevance["is_relevant"]:
            yield {
                "type": "research_source",
                "source": {
                    **source,
                    "id": source_id,
                    "status": "error",
                    "excerpt_preview": excerpt_preview,
                    "summary": "Fonte descartada por nao confirmar o assunto principal.",
                },
            }
            continue

        yield {
            "type": "research_source",
            "source": {
                **source,
                "id": source_id,
                "status": "summarizing",
                "excerpt_preview": excerpt_preview,
                "summary": "",
            },
        }
        try:
            latest_summary = ""
            for event in iter_llm_completion(
                llm,
                messages=build_research_summary_messages(user_question, source, excerpt),
                max_tokens=220,
                temperature=min(temperature, 0.08),
                repeat_penalty=repeat_penalty,
                finalizer=sanitize_llm_text,
                final_doneizer=sanitize_llm_text,
                keep_alive=resolve_ollama_keep_alive(),
            ):
                if event.get("done"):
                    latest_summary = event.get("text", latest_summary).strip()
                    continue

                latest_summary = event.get("text", latest_summary).strip()
                yield {
                    "type": "research_source",
                    "source": {
                        **source,
                        "id": source_id,
                        "status": "summarizing",
                        "excerpt_preview": excerpt_preview,
                        "summary": latest_summary,
                    },
                }
        except Exception as exc:
            yield {
                "type": "research_source",
                "source": {
                    **source,
                    "id": source_id,
                    "status": "error",
                    "excerpt_preview": excerpt_preview,
                    "summary": f"Falha ao resumir: {exc}",
                },
            }
            continue

        if ascii_fold(latest_summary).strip().lower().startswith("irrelevante") or not latest_summary.strip():
            yield {
                "type": "research_source",
                "source": {
                    **source,
                    "id": source_id,
                    "status": "error",
                    "excerpt_preview": excerpt_preview,
                    "summary": "Fonte ignorada por baixa relevancia.",
                },
            }
            continue

        item = {
            "id": source_id,
            "title": source["title"],
            "url": source["url"],
            "domain": source["domain"],
            "query": source.get("query", ""),
            "excerpt_preview": excerpt_preview,
            "summary": latest_summary or "Resumo indisponivel.",
            "status": "ready",
        }
        research_items.append(item)
        log_research_multiline(f"Resumo da fonte | {item['domain']}", item["summary"])
        yield {"type": "research_source", "source": item}

    if research_items:
        yield {
            "type": "research_status",
            "status": "ready",
            "message": f"{len(research_items)} fonte(s) resumida(s).",
        }
        return {
            "items": research_items,
            "context": format_research_context(user_question, research_items),
        }

    yield {
        "type": "research_status",
        "status": "warning",
        "message": "Nao encontrei fontes uteis na web para esse pedido.",
    }
    return {"items": [], "context": build_empty_research_context(user_question)}


def build_chat_messages(messages, research_context="", response_mode="music"):
    if response_mode == "informational":
        system_instruction = (
            "Voce e Lyra, um copiloto musical local. "
            "Responda sempre em Portugues do Brasil. "
            "Nesta resposta, atue em modo informativo e factual. "
            "Responda em texto normal, curto e util. "
            "Se a pergunta for factual, responda diretamente o fato pedido antes de qualquer contexto extra. "
            "Nao gere blocos ```title```, ```style```, ```lyrics```, ```duration``` ou ```language```. "
            "Nao componha musica, nao escreva letra e nao entregue briefing musical, a menos que o usuario peca isso explicitamente. "
            "Nao adivinhe fatos ausentes e nao force conexoes entre pessoas, bandas, premios, musicas ou albuns. "
            "Se houver dossie de pesquisa web, use-o como fonte principal e cite [1], [2], [3] ao mencionar fatos. "
            "Se o dossie disser que faltam fontes confiaveis, admita isso claramente."
        )
    else:
        system_instruction = (
            "Voce e Lyra, um copiloto musical local. "
            "Responda sempre em Portugues do Brasil. "
            "Ajude o usuario a transformar ideias em briefing musical, letra, estrutura, arranjo, "
            "bpm, referencias de voz e comandos claros para gerar musica. "
            "Como os modelos locais podem ser pequenos, seja direto, pratico e evite respostas longas demais. "
            "Quando faltar contexto, faca no maximo uma pergunta curta. "
            "Quando a resposta puder ser usada direto no gerador, entregue blocos curtos em markdown com cercas triplas. "
            "Priorize estes blocos quando fizer sentido, exatamente com estes nomes: ```title```, ```style```, ```lyrics```, ```duration``` e ```language```. "
            "Se estiver montando uma musica quase pronta, prefira responder so com esses blocos, sem texto extra antes ou depois. "
            "Quando devolver esses blocos, inclua sempre o bloco ```language``` com um codigo curto como pt, en, es, fr, ja ou ko. "
            "No bloco ```style```, escreva cada instrucao de ritmo, arranjo, timbre ou voz em uma linha separada entre colchetes, como [guitarra pesada metalica]. "
            "Nao use bullets e nao use rotulos como Genero:, Clima:, Arranjo: ou Voz:. "
            "No bloco ```lyrics```, mantenha tags de secao como [Verse 1], [Chorus] e [Bridge], mas coloque cada linha cantada entre aspas duplas. "
            "Exemplo de formato correto: \"Sol brilha, alegria no ar\". "
            "No bloco ```duration```, envie apenas um numero inteiro em segundos. "
            "Se a conversa for comum e nao for hora de montar musica, responda normalmente."
        )

    normalized = [{"role": "system", "content": system_instruction}]
    if research_context:
        normalized.append({
            "role": "system",
            "content": (
                "Voce recebeu um dossie de pesquisa web preparado antes desta resposta. "
                "Use-o como contexto factual prioritario e nao invente fatos externos quando ele existir. "
                "Se o dossie disser que nao houve fontes confiaveis, admita isso claramente. "
                "Nao exponha o processo interno de pesquisa; apenas aproveite as informacoes e cite [1], [2], [3] quando usar fatos das fontes."
            ),
        })
        normalized.append({"role": "user", "content": research_context})
    for msg in messages[-10:]:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        content = sanitize_llm_text(msg.get("content", "")).strip()
        images = normalize_ollama_images(msg.get("images"))
        if not content and not images:
            continue

        payload = {
            "role": role,
            "content": content or "Considere os arquivos anexados nesta mensagem.",
        }
        if images:
            payload["images"] = images
        normalized.append(payload)
    return normalized


def build_lyrics_messages(*, genre, language, prompt, duration, base_prompt):
    theme = prompt or "amor, memoria, saudade e emocao"
    extra_context = base_prompt.strip() or "Nenhum contexto extra."
    duration = max(10, min(int(duration or 60), 600))

    if duration <= 45:
        structure = ["[Intro]", "[Verse 1]", "[Chorus]", "[Verse 2]", "[Chorus]", "[Outro]"]
        chorus_count = 2
        line_target = "2 a 4 linhas por secao"
    elif duration <= 75:
        structure = ["[Intro]", "[Verse 1]", "[Pre-Chorus]", "[Chorus]", "[Verse 2]", "[Chorus]", "[Bridge]", "[Final Chorus]", "[Outro]"]
        chorus_count = 2
        line_target = "3 a 5 linhas por secao"
    elif duration <= 120:
        structure = ["[Intro]", "[Verse 1]", "[Pre-Chorus]", "[Chorus]", "[Verse 2]", "[Pre-Chorus]", "[Chorus]", "[Bridge]", "[Final Chorus]", "[Outro]"]
        chorus_count = 3
        line_target = "4 a 6 linhas por secao"
    elif duration <= 210:
        structure = ["[Intro]", "[Verse 1]", "[Pre-Chorus]", "[Chorus]", "[Verse 2]", "[Pre-Chorus]", "[Chorus]", "[Verse 3]", "[Bridge]", "[Hook]", "[Final Chorus]", "[Outro]"]
        chorus_count = 3
        line_target = "4 a 6 linhas por secao, com desenvolvimento real"
    else:
        structure = ["[Intro]", "[Verse 1]", "[Pre-Chorus]", "[Chorus]", "[Verse 2]", "[Pre-Chorus]", "[Chorus]", "[Verse 3]", "[Hook]", "[Chorus]", "[Bridge]", "[Final Chorus]", "[Outro]"]
        chorus_count = 4
        line_target = "4 a 8 linhas por secao, com progressao e variacao entre os versos"

    structure_text = "\n".join(f"- {section}" for section in structure)
    return [
        {
            "role": "system",
            "content": (
            "Voce e um compositor especialista em letras cantaveis. "
            "Responda apenas com a letra final, sem explicacoes ou comentarios extras. "
            "Nao explique o processo. "
            "Use tags de secao quando fizer sentido, como [Intro], [Verse 1], [Verse 2], [Pre-Chorus], [Chorus], [Bridge], [Hook], [Final Chorus] e [Outro]. "
            "Toda linha cantada deve vir entre aspas duplas. "
            "Se quiser indicar intencao de arranjo ou entrada instrumental, use uma linha em colchetes, como [synth tropical brilhante]. "
            "A letra precisa soar humana, cantavel, memoravel e pronta para cantar. "
            "Nao omita linhas, nao resuma secoes e nao corte versos no meio. "
            "Entregue a letra completa, com todas as secoes necessarias para a duracao pedida. "
            "Para musicas maiores, mantenha progressao natural e mais de um refrao forte. "
            "Se a duracao alvo passar de 180 segundos, desenvolva melhor a narrativa, varie os versos e evite repetir texto demais."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Crie uma letra para uma musica.\n"
                f"Genero ou estilo: {genre}\n"
                f"Idioma: {language}\n"
                f"Tema principal: {theme}\n"
                f"Duracao alvo: cerca de {duration} segundos\n"
                f"Contexto extra do usuario: {extra_context}\n"
                f"Estrutura sugerida:\n{structure_text}\n"
                f"Quantidade minima de refroes: {chorus_count}\n"
                f"Tamanho ideal: {line_target}\n"
                f"Entrega: apenas a letra final, usando a estrutura sugerida como guia."
            ),
        },
    ]


def resolve_turbo_generation_params(*, duration, infer_steps, guidance_scale, shift_val, ui_mode):
    """Normalize user-facing controls into sane values for the ACE-Step turbo preset."""
    duration = max(10, min(int(duration or 60), 600))
    requested_steps = int(infer_steps or 8)
    requested_cfg = float(guidance_scale or 1.0)
    requested_shift = float(shift_val or 3.0)
    mode = str(ui_mode or "advanced").strip().lower()

    notes = []
    effective_steps = max(4, min(requested_steps, 8))
    effective_cfg = 1.0
    effective_shift = max(1.0, min(requested_shift, 3.0))

    if mode == "simple":
        if duration <= 60:
            effective_steps = 8
        elif duration <= 90:
            effective_steps = 8
        elif duration <= 120:
            effective_steps = 7
        elif duration <= 180:
            effective_steps = 6
        else:
            effective_steps = 5
        effective_shift = 3.0
        notes.append(
            f"Modo simples otimizado para turbo: {effective_steps} passos, CFG 1.0 e shift 3.0."
        )
    else:
        if requested_steps != effective_steps:
            notes.append(
                f"Turbo suporta no maximo 8 passos; ajustado de {requested_steps} para {effective_steps}."
            )

    if requested_cfg != 1.0:
        notes.append("CFG acima de 1.0 nao tem efeito no preset turbo; usando 1.0.")
    if requested_shift != effective_shift:
        notes.append(
            f"Shift {requested_shift:.1f} nao e valido neste preset; usando {effective_shift:.1f}."
        )

    return {
        "steps": effective_steps,
        "cfg": effective_cfg,
        "shift": effective_shift,
        "notes": notes,
    }


def run_llm_completion(
    llm,
    prompt=None,
    *,
    messages=None,
    max_tokens,
    temperature,
    repeat_penalty,
    stop=None,
    finalizer=None,
    keep_alive=None,
    system=None,
):
    finalizer = finalizer or sanitize_llm_text
    cfg = load_app_config()
    resolved_keep_alive = keep_alive if keep_alive is not None else resolve_ollama_keep_alive(cfg)
    payload = {
        "model": llm["model"],
        "stream": False,
        "keep_alive": resolved_keep_alive,
        "options": build_ollama_runtime_options(
            max_tokens=max_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
            stop=stop,
            cfg=cfg,
        ),
    }

    endpoint = "/chat"
    if messages is not None:
        payload["messages"] = messages
    else:
        endpoint = "/generate"
        payload["prompt"] = prompt or ""
        if system:
            payload["system"] = system

    with llm_lock:
        response = ollama_request("POST", endpoint, payload=payload, timeout=(10, 900))
        data = response.json()

    if messages is not None:
        content = data.get("message", {}).get("content", "")
    else:
        content = data.get("response", "")
    return finalizer(content)


def iter_llm_completion(
    llm,
    prompt=None,
    *,
    messages=None,
    max_tokens,
    temperature,
    repeat_penalty,
    stop=None,
    finalizer=None,
    final_doneizer=None,
    keep_alive=None,
    system=None,
):
    finalizer = finalizer or sanitize_llm_text
    final_doneizer = final_doneizer or finalizer
    cfg = load_app_config()
    resolved_keep_alive = keep_alive if keep_alive is not None else resolve_ollama_keep_alive(cfg)

    payload = {
        "model": llm["model"],
        "stream": True,
        "keep_alive": resolved_keep_alive,
        "options": build_ollama_runtime_options(
            max_tokens=max_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
            stop=stop,
            cfg=cfg,
        ),
    }

    endpoint = "/chat"
    if messages is not None:
        payload["messages"] = messages
    else:
        endpoint = "/generate"
        payload["prompt"] = prompt or ""
        if system:
            payload["system"] = system

    assembled = ""
    with llm_lock:
        with ollama_request(
            "POST",
            endpoint,
            payload=payload,
            stream=True,
            timeout=(10, 1800),
        ) as response:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                event = json.loads(raw_line)
                if event.get("error"):
                    raise RuntimeError(event["error"])

                if messages is not None:
                    delta = event.get("message", {}).get("content", "")
                else:
                    delta = event.get("response", "")
                if not delta:
                    continue

                assembled += delta
                yield {
                    "delta": delta,
                    "text": finalizer(assembled),
                }

    yield {
        "done": True,
        "text": final_doneizer(assembled),
    }


def stream_llm_completion(
    llm,
    prompt=None,
    *,
    messages=None,
    max_tokens,
    temperature,
    repeat_penalty,
    stop=None,
    finalizer=None,
    final_doneizer=None,
    keep_alive=None,
    system=None,
):
    finalizer = finalizer or sanitize_llm_text
    final_doneizer = final_doneizer or finalizer

    @stream_with_context
    def generate():
        last_text = ""
        try:
            for event in iter_llm_completion(
                llm,
                prompt=prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                repeat_penalty=repeat_penalty,
                stop=stop,
                finalizer=finalizer,
                final_doneizer=final_doneizer,
                keep_alive=keep_alive,
                system=system,
            ):
                if event.get("done"):
                    last_text = event.get("text", last_text)
                    yield f"data: {json.dumps({'done': True, 'text': last_text}, ensure_ascii=False)}\n\n"
                    continue

                last_text = event.get("text", last_text)
                payload_out = {
                    "delta": event.get("delta", ""),
                    "text": last_text,
                }
                yield f"data: {json.dumps(payload_out, ensure_ascii=False)}\n\n"
        except Exception as exc:
            error_payload = {
                "error": explain_llm_failure(exc),
                "text": last_text,
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return generate()


def normalize_generated_lyrics(text):
    lyrics = sanitize_llm_text(text).strip()

    if lyrics and not lyrics.startswith("["):
        lyrics = "[Verse 1]\n" + lyrics

    lyrics = re.sub(r'(?i)write\s+.*?lyrics.*?\n', '', lyrics)
    lyrics = re.sub(r'(?i)the song is about.*?\n', '', lyrics)
    lyrics = re.sub(r'(?i)style notes:.*?\n', '', lyrics)
    lyrics = re.sub(r'(?i)structure:.*?\n', '', lyrics)
    lyrics = re.sub(r'(?i)example:.*?\n', '', lyrics)
    lyrics = re.sub(r'<[^>]+>', '', lyrics)
    lyrics = re.sub(r'\n{3,}', '\n\n', lyrics).strip()
    lyrics = normalize_quoted_lyric_lines(lyrics)

    if len(lyrics) < 30:
        lyrics = "[Verse 1]\n\"Letras serao guiadas pela geracao musical\"\n\n[Chorus]\n\"Refrao instrumental\""

    return lyrics

def update_status(phase, message, current=0, total=0):
    setup_state.update(phase=phase, message=message, current=current, total=total)
    log.info(f"[{phase}] {message}")


@app.context_processor
def inject_boot_state():
    boot_complete = bool(setup_state.get("complete"))
    boot_phase = setup_state.get("phase") or "idle"
    boot_message = setup_state.get("message") or "Inicializando..."
    return {
        "boot_complete": boot_complete,
        "boot_phase": boot_phase,
        "boot_message": boot_message,
        "boot_overlay_visible": not boot_complete,
    }


# ── Dependency Install ─────────────────────────────────────────────────────
def ensure_package(pkg_import, pip_args):
    """pip_args pode ser string (pacote único) ou lista de strings."""
    try:
        __import__(pkg_import)
    except ImportError:
        if isinstance(pip_args, str):
            pip_args = pip_args.split()
        log.info(f"Instalando {pip_args[0]}...")
        import subprocess
        # Força UTF-8 no subprocess — o Windows usa CP1252 por padrão e quebra pacotes com emoji/acentos no setup.py
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + pip_args, env=env)


# ── Setup Pipeline ─────────────────────────────────────────────────────────
def load_pipeline():
    """Installs deps and loads the ACE-Step pipeline into GPU/CPU."""
    global pipeline

    # ── Passo 1: Clonar o repositório se necessário ─────────────────────────
    ace_src = BASE_DIR / "ace_step_src"
    if not (ace_src / "acestep").exists():
        import subprocess as _sp
        _env = os.environ.copy()
        _env["GIT_TERMINAL_PROMPT"] = "0"
        update_status("setup", "Clonando ACE-Step do GitHub (aguarde)...", 0, 3)
        log.info("Clonando ACE-Step-1.5...")
        _sp.check_call(["git", "clone", "--depth=1",
                        "https://github.com/ace-step/ACE-Step-1.5.git",
                        str(ace_src)], env=_env)
        log.info("Clone concluído!")

    if str(ace_src) not in sys.path:
        sys.path.insert(0, str(ace_src))

    # ── Passo 2: Limpar versões antigas (liberar espaço) e instalar as corretas ──
    import importlib.metadata, subprocess as _pip

    def uninstall_if_wrong_version(pkg_name, required_version_substr):
        try:
            installed = importlib.metadata.version(pkg_name)
            if required_version_substr not in installed:
                log.info(f"Removendo {pkg_name} {installed} (versão errada)...")
                _pip.check_call([sys.executable, "-m", "pip", "uninstall", "-y", pkg_name])
        except importlib.metadata.PackageNotFoundError:
            pass

    update_status("setup", "Limpando versões antigas para liberar espaço...", 1, 3)
    uninstall_if_wrong_version("torch",        "cu128")
    uninstall_if_wrong_version("torchvision",  "cu128")
    uninstall_if_wrong_version("torchaudio",   "cu128")
    uninstall_if_wrong_version("transformers", "4.5")   # mantém apenas 4.51-4.57
    try:
        _pip.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "torchcodec"])
        log.info("Removendo torchcodec (incompatível no Windows sem FFmpeg manual)")
    except Exception:
        pass
    log.info("Limpeza concluída!")

    update_status("setup", "Instalando PyTorch 2.7.1 + CUDA 12.8...", 1, 3)
    ensure_package("torch",
        ["torch==2.7.1+cu128", "torchvision==0.22.1+cu128", "torchaudio==2.7.1+cu128",
         "--index-url", "https://download.pytorch.org/whl/cu128",
         "--upgrade"])

    update_status("setup", "Instalando dependências do ACE-Step...", 2, 3)
    CORE_DEPS = [
        ("transformers",           "transformers>=4.51.0,<4.58.0"),
        ("accelerate",             "accelerate>=0.30"),
        ("diffusers",              "diffusers>=0.37"),
        ("loguru",                 "loguru>=0.7.3"),
        ("einops",                 "einops>=0.8.1"),
        ("peft",                   "peft>=0.18.0"),
        ("vector_quantize_pytorch","vector-quantize-pytorch>=1.27.15"),
        ("librosa",                "librosa"),
        ("soundfile",              "soundfile>=0.13.1"),
        ("tqdm",                   "tqdm"),
        ("gradio",                 "gradio==6.2.0"),
        ("matplotlib",             "matplotlib>=3.7.5"),
        ("scipy",                  "scipy>=1.10.1"),
        ("fastapi",                "fastapi>=0.110.0"),
        ("uvicorn",                "uvicorn[standard]>=0.27.0"),
        ("pydub",                  "pydub"),
        ("imageio_ffmpeg",         "imageio-ffmpeg"),
        ("numba",                  "numba>=0.63.1"),
        ("torchao",                "torchao"),
        ("toml",                   "toml"),
        ("modelscope",             "modelscope"),
    ]
    for mod, pkg in CORE_DEPS:
        ensure_package(mod, [pkg, "--upgrade"])

    update_status("setup", "Verificando Ollama local...", 2, 3)
    global llm_last_error, llm_runtime_notice
    try:
        ensure_ollama_service(timeout=10)
        ollama_version = get_ollama_version() or "desconhecida"
        llm_last_error = None
        selected_llm_id, _, notice = resolve_llm_target(load_app_config(), kind="text")
        selected_model = AVAILABLE_LLMS[selected_llm_id]
        llm_runtime_notice = notice or (
            f"Ollama {ollama_version} online. "
            f"Modelo padrao: {selected_model['title']}."
        )
        log.info(f"Ollama detectado: versao {ollama_version}")
    except Exception as exc:
        llm_last_error = explain_llm_failure(exc)
        llm_runtime_notice = "Ollama indisponivel no boot. A interface vai tentar iniciar e baixar modelos automaticamente."
        log.warning(f"AI Lyrics Engine indisponivel no momento: {llm_last_error}")

    update_status("setup", "Todas as dependencias OK. Carregando modelo na GPU...", 3, 3)

    # ── Passo 3: Carregar o pipeline ─────────────────────────────────────────
    try:
        global pipeline
        import torch
        from acestep.handler import AceStepHandler

        env_device = os.environ.get("LYRA_DEVICE", "").strip().lower()
        if env_device in ["cuda", "cpu"]:
            device = env_device
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
        log.info(f"Dispositivo selecionado: {device.upper()}")

        cfg = load_app_config()
        # Env override has higher precedence than config.json
        env_vram = os.environ.get("LYRA_VRAM_MODE", "").strip().lower()
        vram_mode = env_vram if env_vram else get_music_retention_policy(cfg)

        env_quant = os.environ.get("LYRA_QUANTIZATION", "").strip()
        quantization_val = env_quant if env_quant else None

        offload = False
        use_flash_attention = device == "cuda"
        if device == "cuda":
            total_vram = torch.cuda.get_device_properties(0).total_memory
            total_vram_gb = total_vram / 1024**3
            if vram_mode == "vram":
                offload = False
            elif vram_mode in {"auto", "ram", "unload"}:
                offload = True
            else:
                offload = False
             
            log.info(f"GPU: {torch.cuda.get_device_name(0)} | VRAM: {total_vram // 1024**3} GB | Offload CPU: {offload} (Modo: {vram_mode})")

        update_status("loading", f"Preparando ACE-Step 1.5 na {device.upper()}... (Pode demorar na 1ª vez)", 0, 1)

        project_root = str(BASE_DIR / "ace_step_src")
        pipeline = AceStepHandler()
        init_status, enable_generate = pipeline.initialize_service(
            project_root=project_root,
            config_path="acestep-v15-turbo",
            device=device,
            use_flash_attention=use_flash_attention,
            compile_model=False,
            offload_to_cpu=offload,
            offload_dit_to_cpu=offload,
            quantization=quantization_val,
            prefer_source=None,
        )

        if enable_generate:
            update_status("ready", f"ACE-Step carregado na {device.upper()}! Pronto para gerar músicas.", 1, 1)
            setup_state["complete"] = True
            log.info("Pipeline pronto!")
        else:
            raise Exception(f"Falha na inicialização do serviço: {init_status}")

    except Exception as e:
        log.exception("Erro ao carregar pipeline")
        setup_state["error"] = f"Erro ao carregar ACE-Step: {e}"
        setup_state["phase"] = "error"


def run_setup():
    try:
        cfg = load_app_config()
        if should_lazy_load_music_model(cfg):
            mode = get_music_retention_policy(cfg)
            setup_state["phase"] = "standby"
            setup_state["message"] = "Motor de musica em espera. Ele sera carregado automaticamente na primeira geracao."
            setup_state["current"] = 0
            setup_state["total"] = 0
            setup_state["complete"] = False
            setup_state["error"] = None
            log.info("Modo de musica %s: pipeline sera carregado sob demanda.", mode)
            return
        load_pipeline()
    except Exception as e:
        setup_state["error"] = str(e)
        setup_state["phase"] = "error"
        log.exception("Setup falhou")


# ── Lyrics LLM (Gemma 2B GGUF) ────────────────────────────────────────────

def download_llm_gguf(model_id):
    """Downloads the specific LLM GGUF model if not already present."""
    global llm_downloading
    model_info = AVAILABLE_LLMS.get(model_id)
    if not model_info:
        raise ValueError(f"Modelo {model_id} não encontrado na lista de permitidos.")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / model_info["file"]

    if model_path.exists():
        size_kb = model_path.stat().st_size / 1024
        if size_kb < 1000: # Se for menor que 1MB, eh um erro (provavelmente HTML bajulado)
            log.warning(f"Baixado arquivo corrompido ou HTML (tamanho muito pequeno: {size_kb}KB). Removendo.")
            model_path.unlink()
        else:
            log.info(f"Modelo GGUF já existe: {model_path}")
            return str(model_path)

    llm_downloading = True
    log.info(f"Baixando {model_info['title']} ({model_info['size']})... Isso pode levar alguns minutos.")

    try:
        import urllib.request
        
        # Download with progress
        def _report(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(100, downloaded * 100 // total_size)
                if block_num % 200 == 0:
                    log.info(f"Download {model_info['title']}: {pct}% ({downloaded // (1024*1024)} MB)")

        urllib.request.urlretrieve(model_info["url"], str(model_path), reporthook=_report)
        log.info(f"Download concluído: {model_path}")
        return str(model_path)

    except Exception as e:
        log.exception(f"Falha ao baixar {model_info['title']}")
        if model_path.exists():
            model_path.unlink()
        raise e
    finally:
        llm_downloading = False


def get_llm():
    """Lazy-loads the selected LLM model (singleton, thread-safe)."""
    global llm_last_error, llm_model, loaded_llm_id, llm_runtime_notice

    cfg = load_app_config()
    runtime_version = get_installed_llama_cpp_version()
    target_id, requested_id, compatibility_notice = resolve_llm_target(cfg, runtime_version)

    if llm_model is not None and loaded_llm_id == target_id:
        llm_last_error = None
        llm_runtime_notice = compatibility_notice
        return llm_model

    with llm_lock:
        if llm_model is not None and loaded_llm_id == target_id:
            llm_last_error = None
            llm_runtime_notice = compatibility_notice
            return llm_model

        # Limpa o modelo atual se for diferente
        if llm_model is not None:
            free_llm()

        model_path = download_llm_gguf(target_id)
        if compatibility_notice:
            llm_runtime_notice = compatibility_notice
            log.warning(compatibility_notice)
        else:
            llm_runtime_notice = None

        try:
            configure_llama_cpp_windows_runtime()
            from llama_cpp import Llama
        except Exception as exc:
            llm_last_error = explain_llm_failure(exc)
            raise Exception(llm_last_error) from exc

        cfg = load_app_config()
        preferred_gpu_layers = resolve_llm_gpu_layers(cfg)
        n_threads = max(1, min(8, os.cpu_count() or 4))

        attempts = []
        load_plan = []
        if preferred_gpu_layers != 0:
            load_plan.append(("GPU", preferred_gpu_layers))
        load_plan.append(("CPU", 0))

        model_title = AVAILABLE_LLMS[target_id]["title"]
        for label, n_gpu_layers in load_plan:
            try:
                log.info(f"Carregando {model_title} via llama.cpp em {label} (n_gpu_layers={n_gpu_layers})...")
                llm_model = Llama(
                    model_path=model_path,
                    n_ctx=2048,
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                loaded_llm_id = target_id
                llm_last_error = None
                if requested_id != target_id:
                    log.info(
                        f"Modelo solicitado '{requested_id}' foi substituido por '{target_id}' "
                        "por compatibilidade do runtime no Windows."
                    )
                log.info(f"{model_title} carregado com sucesso em {label}.")
                return llm_model
            except Exception as exc:
                llm_model = None
                attempts.append(f"{label}: {exc}")
                log.warning(f"Falha ao carregar {model_title} em {label}: {exc}")
                time.sleep(1)

        error_summary = " | ".join(attempts) if attempts else "nenhuma tentativa registrada"
        llm_last_error = explain_llm_failure(error_summary)
        raise Exception(llm_last_error)


def free_llm():
    """Libera o modelo LLM da VRAM para dar espaco ao ACE-Step."""
    global llm_model, loaded_llm_id
    if llm_model is not None:
        del llm_model
        llm_model = None
        loaded_llm_id = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                log.info("Gemma liberado da VRAM")
        except Exception:
            pass


def load_app_config():
    """Carrega configuracoes do config.json"""
    merged = dict(DEFAULT_APP_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    merged.update(loaded)
        except Exception:
            pass
    merged["acestep_vram_mode"] = normalize_retention_policy(merged.get("acestep_vram_mode"), default="vram")
    merged["gemma_vram_mode"] = normalize_retention_policy(merged.get("gemma_vram_mode"), default="ram")
    return merged


def save_app_config(data):
    """Salva configuracoes no config.json"""
    payload = dict(DEFAULT_APP_CONFIG)
    if isinstance(data, dict):
        payload.update(data)
    payload["acestep_vram_mode"] = normalize_retention_policy(payload.get("acestep_vram_mode"), default="vram")
    payload["gemma_vram_mode"] = normalize_retention_policy(payload.get("gemma_vram_mode"), default="ram")
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ── Routes ─────────────────────────────────────────────────────────────────

def get_llm(kind="text"):
    """Resolve o modelo atual do Ollama e garante que ele exista localmente."""
    global llm_last_error, llm_model, loaded_llm_id, llm_runtime_notice

    cfg = load_app_config()
    target_id, requested_id, compatibility_notice = resolve_llm_target(cfg, kind=kind)
    model_info = AVAILABLE_LLMS[target_id]

    if llm_model is not None and loaded_llm_id == target_id:
        llm_last_error = None
        llm_runtime_notice = compatibility_notice
        return llm_model

    try:
        ensure_ollama_model(target_id, blocking=True)
        llm_model = dict(model_info, id=target_id)
        loaded_llm_id = target_id
        llm_last_error = None
        llm_runtime_notice = compatibility_notice
        log.info(f"Modelo Ollama ativo: {model_info['title']} ({model_info['model']})")
        if requested_id != target_id:
            log.info(
                f"Modelo solicitado '{requested_id}' foi ajustado para '{target_id}' "
                "por compatibilidade de tipo."
            )
        return llm_model
    except Exception as exc:
        llm_model = None
        loaded_llm_id = None
        llm_last_error = explain_llm_failure(exc)
        raise Exception(llm_last_error) from exc


def stop_ollama_model(model_id=None):
    model_id = model_id or loaded_llm_id
    if not model_id or model_id not in AVAILABLE_LLMS:
        return

    ollama_exe = find_ollama_executable()
    if not ollama_exe:
        return

    model_name = AVAILABLE_LLMS[model_id]["model"]
    try:
        subprocess.run(
            [ollama_exe, "stop", model_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
    except Exception:
        pass


def free_llm():
    """Libera o modelo do Ollama para nao disputar VRAM com o ACE-Step."""
    global llm_model, loaded_llm_id
    stop_ollama_model(loaded_llm_id)
    llm_model = None
    loaded_llm_id = None
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
    except Exception:
        pass


def trim_cuda_cache(reason="manual"):
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
            log.info("Cache CUDA limpo (%s)", reason)
    except Exception:
        pass


def prepare_for_music_generation():
    if loaded_llm_id:
        log.info("Liberando motor de texto antes da geracao musical para evitar disputa de VRAM.")
        free_llm()
    trim_cuda_cache("pre-music-generate")


def ensure_music_pipeline_ready(cfg=None, *, reason="geracao"):
    cfg = cfg or load_app_config()
    if pipeline is not None and setup_state.get("complete"):
        return

    mode = get_music_retention_policy(cfg)
    log.info("Preparando motor de musica sob demanda | modo=%s | motivo=%s", mode, reason)
    load_pipeline()

    if pipeline is None or not setup_state.get("complete"):
        detail = setup_state.get("error") or "Pipeline ainda carregando. Aguarde."
        raise RuntimeError(detail)


def free_music_pipeline(reason="manual"):
    """Libera o ACE-Step da memoria quando a politica for descarregar completamente."""
    global pipeline
    if pipeline is None:
        return

    try:
        del pipeline
    except Exception:
        pass
    pipeline = None

    try:
        import gc
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    setup_state["phase"] = "standby"
    setup_state["message"] = "Motor de musica descarregado para economizar VRAM."
    setup_state["current"] = 0
    setup_state["total"] = 0
    setup_state["complete"] = False
    setup_state["error"] = None
    log.info("ACE-Step descarregado (%s)", reason)


@app.route("/")
def index():
    return render_template("app_shell.html", active_page="criar")

@app.route("/feed")
def feed():
    return render_template("app_shell.html", active_page="feed")

@app.route("/configuracoes")
def config_page():
    return render_template("app_shell.html", active_page="config")

@app.route("/chat")
def chat():
    return render_template("app_shell.html", active_page="chat")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/setup-status")
def api_setup_status():
    return jsonify(setup_state)


@app.route("/api/health")
def api_health():
    if pipeline is not None and setup_state.get("complete"):
        info = {"status": "online"}
        try:
            import torch
            if torch.cuda.is_available():
                info["gpu"] = torch.cuda.get_device_name(0)
        except Exception:
            pass
        return jsonify(info)
    if pipeline is None and setup_state.get("phase") == "standby":
        return jsonify({"status": "standby", "phase": "standby"}), 200
    return jsonify({"status": "loading", "phase": setup_state["phase"]}), 503


@app.route("/api/llm/status")
def api_llm_status():
    """Retorna o status do Ollama e dos modelos configurados na interface."""
    results = {}
    cfg = load_app_config()
    current_selected, requested_selected, compatibility_notice = resolve_llm_target(cfg, kind="text")
    vision_selected, requested_vision_selected, vision_notice = resolve_llm_target(cfg, kind="vision")

    local_models = {}
    runtime_error = llm_last_error
    runtime_version = None
    try:
        runtime_version = get_ollama_version()
        local_models = list_local_ollama_models()
        runtime_error = None
    except Exception as exc:
        runtime_error = explain_llm_failure(exc)

    for m_id, m_info in AVAILABLE_LLMS.items():
        model_name = m_info["model"]
        pull_state = llm_pull_status.get(m_id, {})
        installed = model_name in local_models
        is_ready = loaded_llm_id == m_id

        status = pull_state.get("status") or "not_downloaded"
        if is_ready:
            status = "ready"
        elif installed:
            status = "downloaded"

        results[m_id] = {
            "title": m_info["title"],
            "model": model_name,
            "size": m_info["size"],
            "kind": m_info.get("kind", "text"),
            "description": m_info.get("description", ""),
            "status": status,
            "selected": (m_id == current_selected),
            "selected_vision": (m_id == vision_selected),
            "requested": (m_id == requested_selected),
            "requested_vision": (m_id == requested_vision_selected),
            "supported": True,
            "support_reason": None,
            "installed": installed,
            "progress": pull_state.get("progress"),
            "error": pull_state.get("error"),
        }
    return jsonify({
        "models": results,
        "runtime_error": runtime_error,
        "runtime_version": runtime_version,
        "notice": llm_runtime_notice or compatibility_notice or vision_notice,
        "engine": "ollama",
        "engine_label": f"Ollama {runtime_version}" if runtime_version else "Ollama offline",
    })

@app.route("/api/llm/download", methods=["POST"])
def api_llm_download():
    data = request.get_json() or {}
    model_id = data.get("model_id")
    if model_id not in AVAILABLE_LLMS:
        return jsonify({"error": "Model invalido."}), 400
    try:
        ensure_ollama_service(timeout=10)
        started = start_model_pull(model_id)
        if not started:
            return jsonify({"success": True, "message": "Esse modelo ja esta sendo preparado."})
        return jsonify({"success": True, "message": "Preparacao do modelo iniciada no Ollama."})
    except Exception as exc:
        return jsonify({"error": explain_llm_failure(exc)}), 500


@app.route("/api/generate-lyrics", methods=["POST"])
def api_generate_lyrics():
    """Gera letras de musica usando Gemma 2B GGUF via few-shot completion."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON necessario"}), 400

    genre       = data.get("genre", "pop").strip()
    user_prompt = data.get("prompt", "").strip()
    base_prompt = data.get("base_prompt", "").strip()
    max_tokens  = int(data.get("max_tokens", 512))

    # Read specifically from config so backend overrides correctly without forcing front-end
    cfg = load_app_config()
    language    = resolve_vocal_language(data.get("language"), cfg)
    temperature = float(data.get("temperature", cfg.get("llm_temperature", 1.05)))
    repeat_penalty = float(data.get("repeat_penalty", cfg.get("llm_repeat_penalty", 1.1)))
    duration    = int(data.get("duration", 60))

    # Calcula tokens baseado na duracao
    if duration <= 30:
        calc_tokens = min(max_tokens, 250)
    elif duration <= 60:
        calc_tokens = min(max_tokens, 400)
    elif duration <= 120:
        calc_tokens = min(max_tokens, 550)
    else:
        calc_tokens = min(max_tokens, 700)

    log.info(f"Gerando letras: genre='{genre}', lang='{language}', dur={duration}s, tokens={calc_tokens}")

    keep_alive = resolve_ollama_keep_alive(cfg)

    try:
        llm = get_llm()

        # ── Few-shot completion prompt ──────────────────────
        # Para modelos pequenos: NAO dar instrucoes, dar EXEMPLO e pedir pra continuar
        theme = user_prompt or "life and feelings"
        lang_name = "Portuguese" if "ortug" in language else language

        prompt_prefix = base_prompt.strip()
        final_prompt = f"""Song: "{genre} about {theme}" ({lang_name})

[Verse 1]
"""
        if prompt_prefix:
            final_prompt = prompt_prefix + "\n\n" + final_prompt

        generated_text = run_llm_completion(
            llm,
            final_prompt,
            max_tokens=calc_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
            stop=["[Verse", "\n\n\n"],
            keep_alive=keep_alive,
        )

        # ── Limpeza MUITO agressiva ──────────────────────────
        lyrics = "[Verse 1]\n" + sanitize_llm_text(generated_text).strip()

        # Remove qualquer coisa que pareca eco do prompt
        lyrics = re.sub(r'(?i)write\s+.*?lyrics.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)the song is about.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)style notes:.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)structure:.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)each verse should.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)write only.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)example:.*?\n', '', lyrics)
        lyrics = re.sub(r'(?i)song:.*?\n', '', lyrics)

        # Remove tags HTML/XML
        lyrics = re.sub(r'<[^>]+>', '', lyrics)
        # Remove tokens degenerados
        lyrics = re.sub(r'\[\?\]', '', lyrics)
        lyrics = re.sub(r'\[…\]', '', lyrics)
        lyrics = re.sub(r'\(\?\)', '', lyrics)

        # Processa linha por linha
        lines = lyrics.split('\n')
        clean_lines = []
        seen_content = set()
        for line in lines:
            stripped = line.strip()

            # Pula linhas vazias consecutivas
            if not stripped:
                if clean_lines and not clean_lines[-1].strip():
                    continue
                clean_lines.append("")
                continue

            # Se a linha eh so uma tag vazia tipo [Verse 1] sem conteudo depois,
            # e a proxima tambem eh tag, pula (secoes vazias)
            # Isso eh tratado abaixo

            # Pula linhas que sao so pontuacao
            if not re.search(r'[a-zA-ZÀ-ÿ]', stripped) and not stripped.startswith('['):
                continue

            # Detecta repeticao de blocos (se a linha ja apareceu 3+ vezes)
            if stripped in seen_content and not stripped.startswith('['):
                continue
            seen_content.add(stripped)

            clean_lines.append(line)

        # Remove secoes vazias (tag seguida de outra tag sem conteudo)
        final_lines = []
        for i, line in enumerate(clean_lines):
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                # Verifica se a proxima linha nao-vazia tambem eh uma tag
                next_content = None
                for j in range(i + 1, len(clean_lines)):
                    if clean_lines[j].strip():
                        next_content = clean_lines[j].strip()
                        break
                # Se a proxima linha eh outra tag ou nao existe, essa secao eh vazia
                if next_content is None or (next_content.startswith('[') and next_content.endswith(']')):
                    continue
            final_lines.append(line)

        lyrics = '\n'.join(final_lines).strip()

        # Remove linhas vazias no final
        while lyrics.endswith('\n\n'):
            lyrics = lyrics[:-1]

        # Se ficou muito curto (modelo falhou), gera letras padrao
        if len(lyrics) < 30:
            log.warning(f"Letras muito curtas ({len(lyrics)} chars), usando fallback")
            lyrics = f"[Verse 1]\n(Letras serao geradas pelo modelo de musica)\n\n[Chorus]\n(Refrão instrumental)"

        log.info(f"Letras geradas com sucesso ({len(lyrics)} caracteres)")
        return jsonify({"lyrics": lyrics})

    except Exception as e:
        log.exception("Falha ao gerar letras")
        error_msg = str(e)
        if "download" in error_msg.lower() or "connection" in error_msg.lower():
            error_msg = f"Falha ao baixar modelo Gemma 2B. Verifique sua conexao. ({e})"
        return jsonify({"error": f"Falha na geracao de letras: {error_msg}"}), 500
    finally:
        if should_unload_text_model(cfg):
            free_llm()


@app.route("/api/chat-legacy", methods=["POST"])
def api_chat_legacy():
    """Geração de mensagens de chat com o modelo instrucional. Suporta streaming via SSE."""
    data = request.get_json()
    messages = data.get("messages", []) if data else []
    
    # Aceitar tanto {"messages": [...]} quanto {"message": "texto"}
    if not messages and data and data.get("message"):
        messages = [{"role": "user", "content": data["message"]}]
    
    if not messages:
        return jsonify({"success": False, "error": "Mensagem vazia."}), 400
    
    # Pegar a ultima mensagem do usuario
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "").strip()
            break
    
    if not last_user_msg:
        return jsonify({"success": False, "error": "Nenhuma mensagem do usuário encontrada."}), 400
    
    stream = data.get("stream", False) if data else False
    
    try:
        llm = get_llm()
        cfg = load_app_config()
        temperature = float(cfg.get("llm_temperature", 0.7))
        repeat_penalty = float(cfg.get("llm_repeat_penalty", 1.1))
        
        # Construir prompt multi-turn no formato Gemma Instruct
        prompt_parts = []
        for m in messages[-6:]:  # Últimas 6 msgs para contexto
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                prompt_parts.append(f"<start_of_turn>user\n{content}<end_of_turn>")
            elif role == "assistant":
                prompt_parts.append(f"<start_of_turn>model\n{content}<end_of_turn>")
        
        # System prompt embutido na primeira mensagem
        system_instruction = "Você é Lyra, uma assistente de IA especialista em composição musical, produção de áudio e teoria musical. Responda sempre em Português de forma clara e útil."
        full_prompt = f"<bos><start_of_turn>user\n{system_instruction}<end_of_turn>\n" + "\n".join(prompt_parts) + "\n<start_of_turn>model\n"
        
        if stream:
            # Streaming via Server-Sent Events
            from flask import Response
            
            def generate_stream():
                try:
                    for token_data in llm(
                        full_prompt,
                        max_tokens=800,
                        temperature=temperature,
                        repeat_penalty=repeat_penalty,
                        stop=["<end_of_turn>", "<start_of_turn>"],
                        echo=False,
                        stream=True
                    ):
                        chunk = token_data["choices"][0].get("text", "")
                        if chunk:
                            yield f"data: {json.dumps({'token': chunk})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return Response(generate_stream(), mimetype="text/event-stream",
                          headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        else:
            # Non-streaming (resposta completa)
            output = llm(
                full_prompt,
                max_tokens=800,
                temperature=temperature,
                repeat_penalty=repeat_penalty,
                stop=["<end_of_turn>", "<start_of_turn>"],
                echo=False
            )
            
            response_text = output["choices"][0]["text"].strip()
            return jsonify({"success": True, "reply": response_text})
        
    except Exception as e:
        log.exception("Falha no chat LLM")
        return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Gera mensagens do chat do Lyra e suporta streaming SSE."""
    data = request.get_json()
    messages = data.get("messages", []) if data else []

    if not messages and data and data.get("message"):
        messages = [{"role": "user", "content": data["message"]}]

    if not messages:
        return jsonify({"success": False, "error": "Mensagem vazia."}), 400

    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "").strip()
            break

    if not last_user_msg:
        return jsonify({"success": False, "error": "Nenhuma mensagem do usuario encontrada."}), 400

    stream = bool(data.get("stream", False)) if data else False

    try:
        llm = get_llm()
        cfg = load_app_config()
        temperature = float(cfg.get("llm_temperature", 0.7))
        repeat_penalty = float(cfg.get("llm_repeat_penalty", 1.1))
        full_prompt = build_chat_prompt(messages)

        if stream:
            return Response(
                stream_llm_completion(
                    llm,
                    full_prompt,
                    max_tokens=800,
                    temperature=temperature,
                    repeat_penalty=repeat_penalty,
                    stop=["<end_of_turn>", "<start_of_turn>"],
                    finalizer=sanitize_llm_text,
                ),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        response_text = sanitize_llm_text(
            run_llm_completion(
                llm,
                full_prompt,
                max_tokens=800,
                temperature=temperature,
                repeat_penalty=repeat_penalty,
                stop=["<end_of_turn>", "<start_of_turn>"],
            )
        ).strip()
        return jsonify({"success": True, "reply": response_text})

    except Exception as exc:
        log.exception("Falha no chat LLM")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Geração de música usando ACE-Step Python nativo."""
    cfg = load_app_config()
    music_retention = get_music_retention_policy(cfg)
    prepare_for_music_generation()
    if pipeline is None or not setup_state.get("complete"):
        try:
            ensure_music_pipeline_ready(cfg, reason="geracao")
        except Exception as exc:
            log.exception("Falha ao preparar pipeline para geracao")
            return jsonify({"error": f"Falha ao carregar motor de musica: {exc}"}), 503
        if pipeline is None or not setup_state.get("complete"):
            return jsonify({"error": "Pipeline ainda carregando. Aguarde."}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON não encontrado"}), 400

    caption = data.get("caption", "").strip()
    if not caption:
        return jsonify({"error": "O campo 'caption' é obrigatório"}), 400

    try:
        import torch

        # Parâmetros de geração
        lyrics          = data.get("lyrics", "")
        duration        = int(data.get("duration", 60))
        language        = resolve_vocal_language(data.get("vocal_language") or data.get("language"), cfg)
        infer_steps     = int(data.get("inference_steps", 25))
        guidance_scale  = float(data.get("cfg_scale", 10.0))
        shift_val       = float(data.get("shift", 4.0))
        batch_size      = int(data.get("batch_size", 1))
        seed_val        = int(data.get("seed", -1))
        ui_mode         = data.get("ui_mode", "advanced")

        tuned_params = resolve_turbo_generation_params(
            duration=duration,
            infer_steps=infer_steps,
            guidance_scale=guidance_scale,
            shift_val=shift_val,
            ui_mode=ui_mode,
        )
        infer_steps = tuned_params["steps"]
        guidance_scale = tuned_params["cfg"]
        shift_val = tuned_params["shift"]

        log.info(
            f"Gerando: '{caption[:80]}...' | {duration}s | Batch: {batch_size} | Seed: {seed_val} | "
            f"Mode: {ui_mode} | Steps: {infer_steps} | CFG: {guidance_scale} | Shift: {shift_val}"
        )
        update_status("generating", f"Gerando '{caption[:50]}...'", 0, 1)

        # Preserva a letra completa e so normaliza formato/tags para o ACE-Step seguir melhor.
        if lyrics:
            lyrics = normalize_generation_lyrics(lyrics)

        caption = normalize_generation_caption(caption)

        if lyrics:
            lyric_guidance = (
                "follow the provided lyrics exactly, preserve every lyric line and section in order, "
                "do not skip verses, clear lead vocals"
            )
            if caption:
                caption = f"{lyric_guidance}, {caption}"
            else:
                caption = lyric_guidance

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_slug = re.sub(r"[^\w\s-]", "", data.get("title", "song"))[:40].strip().replace(" ", "_") or "song"
        wav_name = f"{title_slug}_{ts}.wav"
        wav_path = OUTPUT_DIR / wav_name

        # Carrega referencia vocal se existir
        ref_audio_str = None
        ref_audio_path = data.get("reference_audio", "")
        if ref_audio_path:
            ref_path = MODELS_DIR / "voices" / Path(ref_audio_path).name
            if ref_path.exists():
                ref_audio_str = str(ref_path)
                log.info(f"Usando referencia vocal: {ref_path.name}")

        # Gera o áudio usando a nova API do ACE-Step 1.5
        gen_kwargs = dict(
            captions=caption,
            lyrics=lyrics,
            audio_duration=float(duration),
            inference_steps=infer_steps,
            guidance_scale=guidance_scale,
            vocal_language=language,
            shift=shift_val,
            batch_size=batch_size,
            seed=seed_val,
        )
        if ref_audio_str:
            gen_kwargs["reference_audio"] = ref_audio_str

        result = pipeline.generate_music(**gen_kwargs)

        if not result.get("success", False):
            raise Exception(result.get("error") or result.get("status_message") or "Erro desconhecido na geração")

        # Salva o áudio
        import soundfile as sf
        import numpy as np
        
        saved_files = []
        for i, audio_dict in enumerate(result["audios"]):
            sample_rate = audio_dict["sample_rate"]
            audio_tensor = audio_dict["tensor"]
            
            # Converte para numpy flutuante
            audio_np = audio_tensor.detach().cpu().numpy()
            
            # soundfile requer shape [samples, channels] para stereo
            if audio_np.ndim == 2 and audio_np.shape[0] == 2:
                audio_np = audio_np.T
                
            suffix = f"_{i+1}" if batch_size > 1 else ""
            current_wav_name = f"{title_slug}_{ts}{suffix}.wav"
            current_wav_path = OUTPUT_DIR / current_wav_name
                
            sf.write(str(current_wav_path), audio_np, sample_rate)
            log.info(f"Áudio salvo: {current_wav_name}")

            # Salva metadados
            meta = {
                "title":      data.get("title", "Sem título") + (f" (Take {i+1})" if batch_size > 1 else ""),
                "caption":    caption,
                "lyrics":     lyrics,
                "duration":   duration,
                "language":   language,
                "filename":   current_wav_name,
                "created_at": datetime.now().isoformat(),
            }
            with open(current_wav_path.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            
            saved_files.append(current_wav_name)

        update_status("ready", "Música gerada com sucesso!", 1, 1)
        response = jsonify({
            "success": True,
            "files": saved_files,
            "effective_params": {
                "inference_steps": infer_steps,
                "cfg_scale": guidance_scale,
                "shift": shift_val,
                "duration": duration,
                "ui_mode": ui_mode,
            },
            "tuning_notes": tuned_params["notes"],
        })
        trim_cuda_cache("post-generate-success")
        if should_unload_music_model(cfg):
            free_music_pipeline("post-generate")
        return response

    except Exception as e:
        trim_cuda_cache("post-generate-error")
        log.exception("Geração falhou")
        update_status("ready", "Erro na geração. Tente novamente.", 1, 1)
        error_message = str(e)
        if "Insufficient free VRAM" in error_message:
            error_message += (
                " O motor de texto ja foi pausado antes da geracao, mas o ACE-Step ainda ficou sem VRAM livre. "
                "Tente reduzir a duracao, usar o modo automatico/cache na RAM/descarregar completamente ou reiniciar os motores."
            )
        return jsonify({"error": error_message}), 500


@app.route("/api/songs")
def api_songs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    songs = []
    for meta_file in OUTPUT_DIR.glob("*.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            wav = OUTPUT_DIR / meta.get("filename", "")
            if wav.exists():
                meta["size_mb"] = round(wav.stat().st_size / (1024 * 1024), 1)
                songs.append(meta)
        except Exception:
            pass
    # Ordena pela data de criacao (mais recente primeiro)
    songs.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return jsonify(songs)


@app.route("/api/songs/<filename>")
def api_song_file(filename):
    safe = Path(filename).name
    filepath = OUTPUT_DIR / safe
    if filepath.exists() and filepath.suffix in (".wav", ".mp3"):
        mime = "audio/wav" if safe.endswith(".wav") else "audio/mpeg"
        return send_file(filepath, mimetype=mime)
    return jsonify({"error": "Arquivo não encontrado"}), 404


@app.route("/api/songs/<filename>", methods=["DELETE"])
def api_delete_song(filename):
    safe = Path(filename).name
    wav  = OUTPUT_DIR / safe
    meta = wav.with_suffix(".json")
    if wav.exists():  wav.unlink()
    if meta.exists(): meta.unlink()
    return jsonify({"success": True})


@app.route("/api/upload-voice", methods=["POST"])
def api_upload_voice():
    """Upload de arquivo de referencia vocal para voice cloning."""
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Arquivo sem nome"}), 400

    # Valida extensao
    ext = Path(file.filename).suffix.lower()
    if ext not in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
        return jsonify({"error": "Formato nao suportado. Use WAV, MP3, FLAC, OGG ou M4A."}), 400

    voices_dir = MODELS_DIR / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r'[^\w\s.-]', '', Path(file.filename).stem)[:50] + ext
    save_path = voices_dir / safe_name
    file.save(str(save_path))

    # Converte arquivos MP3/M4A/FLAC/OGG para WAV transparente
    if ext != ".wav":
        try:
            import pydub
            import imageio_ffmpeg
            pydub.AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
            audio = pydub.AudioSegment.from_file(str(save_path))
            # Padroniza p/ garantir compatibilidade maxima com PyTorch
            audio = audio.set_channels(1).set_frame_rate(48000)
            new_safe_name = Path(safe_name).stem + ".wav"
            new_save_path = voices_dir / new_safe_name
            audio.export(str(new_save_path), format="wav")
            # Deleta o original
            save_path.unlink()
            safe_name = new_safe_name
            save_path = new_save_path
            log.info(f"Voz auto-convertida para WAV: {safe_name}")
        except Exception as e:
            log.warning(f"Aviso na conversao de voz (reinicie o app p/ baixar pydub se necessario): {e}")

    log.info(f"Voz salva: {safe_name} ({save_path.stat().st_size / 1024:.0f} KB)")
    return jsonify({"success": True, "filename": safe_name})


@app.route("/api/voices")
def api_voices():
    """Lista as vozes de referencia disponíveis."""
    voices_dir = MODELS_DIR / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    voices = []
    for f in voices_dir.iterdir():
        if f.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
            voices.append({
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return jsonify(voices)


@app.route("/api/voices/<filename>", methods=["DELETE"])
def api_delete_voice(filename):
    """Deleta uma voz de referencia."""
    safe = Path(filename).name
    voice_path = MODELS_DIR / "voices" / safe
    if voice_path.exists():
        voice_path.unlink()
    return jsonify({"success": True})


@app.route("/api/extend", methods=["POST"])
def api_extend_song():
    """Estende uma musica existente gerando mais audio e concatenando."""
    cfg = load_app_config()
    music_retention = get_music_retention_policy(cfg)
    prepare_for_music_generation()
    if pipeline is None or not setup_state.get("complete"):
        try:
            ensure_music_pipeline_ready(cfg, reason="extensao")
        except Exception as exc:
            log.exception("Falha ao preparar pipeline para extensao")
            return jsonify({"error": f"Falha ao carregar motor de musica: {exc}"}), 503
        if pipeline is None or not setup_state.get("complete"):
            return jsonify({"error": "Pipeline ainda carregando. Aguarde."}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON necessario"}), 400

    source_file = data.get("filename", "").strip()
    extend_duration = int(data.get("duration", 30))
    caption = data.get("caption", "").strip()

    if not source_file:
        return jsonify({"error": "Arquivo de origem necessario"}), 400

    src_path = OUTPUT_DIR / Path(source_file).name
    if not src_path.exists():
        return jsonify({"error": "Arquivo nao encontrado"}), 404

    try:
        import soundfile as sf
        import numpy as np

        # Le o audio original
        original_audio, original_sr = sf.read(str(src_path))

        # Le metadados originais
        meta_path = src_path.with_suffix(".json")
        original_meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                original_meta = json.load(f)

        if not caption:
            caption = original_meta.get("caption", "music")
        lyrics = original_meta.get("lyrics", "")
        language = resolve_vocal_language(original_meta.get("language"), cfg)

        log.info(f"Estendendo '{source_file}' +{extend_duration}s")
        update_status("generating", f"Estendendo musica +{extend_duration}s...", 0, 1)

        # Gera nova parte
        result = pipeline.generate_music(
            captions=caption,
            lyrics=lyrics,
            audio_duration=float(extend_duration),
            inference_steps=8,
            guidance_scale=7.0,
            vocal_language=language,
            shift=3.0,
            batch_size=1,
            seed=-1,
        )

        if not result.get("success", False):
            raise Exception(result.get("error") or "Falha na extensao")

        # Concatena os audios
        new_audio = result["audios"][0]["tensor"].detach().cpu().numpy()
        new_sr = result["audios"][0]["sample_rate"]

        if new_audio.ndim == 2 and new_audio.shape[0] == 2:
            new_audio = new_audio.T

        # Resample se necessario
        if new_sr != original_sr:
            log.warning(f"Sample rates diferentes: {original_sr} vs {new_sr}")

        # Crossfade suave (0.5s)
        crossfade_samples = min(int(original_sr * 0.5), len(original_audio), len(new_audio))
        if crossfade_samples > 0:
            fade_out = np.linspace(1, 0, crossfade_samples)
            fade_in = np.linspace(0, 1, crossfade_samples)
            if original_audio.ndim == 2:
                fade_out = fade_out[:, np.newaxis]
                fade_in = fade_in[:, np.newaxis]
            original_audio[-crossfade_samples:] *= fade_out
            new_audio[:crossfade_samples] *= fade_in
            combined = np.concatenate([original_audio, new_audio[crossfade_samples:]])
        else:
            combined = np.concatenate([original_audio, new_audio])

        # Salva o arquivo estendido (sobrescreve o original)
        sf.write(str(src_path), combined, original_sr)

        # Atualiza metadados
        new_duration = len(combined) / original_sr
        original_meta["duration"] = int(new_duration)
        original_meta["size_mb"] = round(src_path.stat().st_size / (1024 * 1024), 1)
        original_meta["title"] = original_meta.get("title", "Sem titulo") + " (Estendida)" if "Estendida" not in original_meta.get("title", "") else original_meta.get("title", "")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(original_meta, f, indent=2, ensure_ascii=False)

        update_status("ready", "Musica estendida com sucesso!", 1, 1)
        log.info(f"Musica estendida: {new_duration:.0f}s total")
        response = jsonify({"success": True, "duration": int(new_duration)})
        trim_cuda_cache("post-extend-success")
        if should_unload_music_model(cfg):
            free_music_pipeline("post-extend")
        return response

    except Exception as e:
        trim_cuda_cache("post-extend-error")
        log.exception("Extensao falhou")
        update_status("ready", "Erro na extensao.", 1, 1)
        error_message = str(e)
        if "Insufficient free VRAM" in error_message:
            error_message += (
                " O motor de texto ja foi pausado antes da extensao, mas o ACE-Step ainda ficou sem VRAM livre. "
                "Tente reduzir a duracao extra ou usar o modo automatico/cache na RAM."
            )
        return jsonify({"error": error_message}), 500


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Retorna as configuracoes salvas."""
    return jsonify(load_app_config())


@app.route("/api/config", methods=["POST"])
def api_set_config():
    """Salva configuracoes."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON necessario"}), 400
    save_app_config(data)
    log.info("Configuracoes salvas com sucesso")
    return jsonify({"success": True})


@app.route("/api/reload-engines", methods=["POST"])
def api_reload_engines():
    """Recarrega os modelos de IA usando as novas configuracoes de VRAM."""
    global pipeline
    
    update_status("setup", "Iniciando recarregamento dos motores...", 0, 3)
    
    try:
        # Tenta liberar VRAM atual
        free_llm()
        if pipeline is not None:
            del pipeline
            pipeline = None
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except Exception as e:
        log.warning(f"Aviso ao liberar memoria antes do reload: {e}")

    # Roda async para nao travar a request HTTP
    threading.Thread(target=run_setup, daemon=True).start()
    return jsonify({"success": True, "message": "Recarregando em background. Aguarde a interface voltar a ficar 'Online'."})


def api_llm_status_ollama():
    results = {}
    cfg = load_app_config()
    current_selected, requested_selected, compatibility_notice = resolve_llm_target(cfg, kind="text")
    vision_selected, requested_vision_selected, vision_notice = resolve_llm_target(cfg, kind="vision")

    local_models = {}
    runtime_error = llm_last_error
    runtime_version = None
    try:
        runtime_version = get_ollama_version()
        local_models = list_local_ollama_models()
        runtime_error = None
    except Exception as exc:
        runtime_error = explain_llm_failure(exc)

    for m_id, m_info in AVAILABLE_LLMS.items():
        model_name = m_info["model"]
        pull_state = llm_pull_status.get(m_id, {})
        installed = model_name in local_models
        is_ready = loaded_llm_id == m_id
        status = pull_state.get("status") or "not_downloaded"
        if is_ready:
            status = "ready"
        elif installed:
            status = "downloaded"

        results[m_id] = {
            "title": m_info["title"],
            "model": model_name,
            "size": m_info["size"],
            "kind": m_info.get("kind", "text"),
            "description": m_info.get("description", ""),
            "status": status,
            "selected": (m_id == current_selected),
            "selected_vision": (m_id == vision_selected),
            "requested": (m_id == requested_selected),
            "requested_vision": (m_id == requested_vision_selected),
            "supported": True,
            "support_reason": None,
            "installed": installed,
            "progress": pull_state.get("progress"),
            "error": pull_state.get("error"),
        }

    return jsonify({
        "models": results,
        "runtime_error": runtime_error,
        "runtime_version": runtime_version,
        "notice": llm_runtime_notice or compatibility_notice or vision_notice,
        "engine": "ollama",
        "engine_label": f"Ollama {runtime_version}" if runtime_version else "Ollama offline",
    })


def api_llm_download_ollama():
    data = request.get_json() or {}
    model_id = data.get("model_id")
    if model_id not in AVAILABLE_LLMS:
        return jsonify({"error": "Model invalido."}), 400

    try:
        ensure_ollama_service(timeout=10)
        started = start_model_pull(model_id)
        if not started:
            return jsonify({"success": True, "message": "Esse modelo ja esta sendo preparado."})
        return jsonify({"success": True, "message": "Preparacao do modelo iniciada no Ollama."})
    except Exception as exc:
        return jsonify({"error": explain_llm_failure(exc)}), 500


def api_generate_lyrics_ollama():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON necessario"}), 400

    genre = data.get("genre", "pop").strip()
    user_prompt = data.get("prompt", "").strip()
    base_prompt = data.get("base_prompt", "").strip()
    max_tokens = int(data.get("max_tokens", 1024))

    cfg = load_app_config()
    language = resolve_vocal_language(data.get("language"), cfg)
    temperature = float(data.get("temperature", cfg.get("llm_temperature", 1.05)))
    repeat_penalty = float(data.get("repeat_penalty", cfg.get("llm_repeat_penalty", 1.1)))
    duration = max(10, min(int(data.get("duration", 90)), 600))
    stream = bool(data.get("stream", False))
    keep_alive = resolve_ollama_keep_alive(cfg)

    if duration <= 30:
        calc_tokens = max(max_tokens, 320)
    elif duration <= 60:
        calc_tokens = max(max_tokens, 520)
    elif duration <= 120:
        calc_tokens = max(max_tokens, 900)
    elif duration <= 180:
        calc_tokens = max(max_tokens, 1200)
    else:
        calc_tokens = max(max_tokens, 1500)
    calc_tokens = min(calc_tokens, 1800)

    log.info(f"Gerando letras via Ollama: genre='{genre}', lang='{language}', dur={duration}s, tokens={calc_tokens}")

    try:
        llm = get_llm(kind="text")
        messages = build_lyrics_messages(
            genre=genre,
            language=language,
            prompt=user_prompt,
            duration=duration,
            base_prompt=base_prompt,
        )
        if stream:
            return Response(
                stream_llm_completion(
                    llm,
                    messages=messages,
                    max_tokens=calc_tokens,
                    temperature=temperature,
                    repeat_penalty=repeat_penalty,
                    stop=["\n\n\n"],
                    finalizer=sanitize_llm_text,
                    final_doneizer=normalize_generated_lyrics,
                    keep_alive=keep_alive,
                ),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        lyrics = normalize_generated_lyrics(run_llm_completion(
            llm,
            messages=messages,
            max_tokens=calc_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
            stop=["\n\n\n"],
            finalizer=sanitize_llm_text,
            keep_alive=keep_alive,
        ))

        if len(lyrics) < 30:
            lyrics = "[Verse 1]\n\"Letras serao guiadas pela geracao musical\"\n\n[Chorus]\n\"Refrao instrumental\""

        return jsonify({"lyrics": lyrics})
    except Exception as exc:
        log.exception("Falha ao gerar letras com Ollama")
        return jsonify({"error": f"Falha na geracao de letras: {str(exc)}"}), 500
    finally:
        if should_unload_text_model(cfg):
            free_llm()


def api_chat_ollama():
    data = request.get_json()
    messages = data.get("messages", []) if data else []

    if not messages and data and data.get("message"):
        messages = [{"role": "user", "content": data["message"]}]

    if not messages:
        return jsonify({"success": False, "error": "Mensagem vazia."}), 400

    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "").strip()
            break

    if not last_user_msg:
        return jsonify({"success": False, "error": "Nenhuma mensagem do usuario encontrada."}), 400

    stream = bool(data.get("stream", False)) if data else False
    has_images = any(normalize_ollama_images(msg.get("images")) for msg in messages if isinstance(msg, dict))
    web_search_enabled = bool(data.get("web_search_enabled", False)) if data else False
    web_search_level = get_web_research_level(data.get("web_search_level", WEB_RESEARCH_DEFAULT_LEVEL) if data else WEB_RESEARCH_DEFAULT_LEVEL)

    try:
        cfg = load_app_config()
        temperature = float(cfg.get("llm_temperature", 0.75))
        repeat_penalty = float(cfg.get("llm_repeat_penalty", 1.1))
        research_bundle = {"items": [], "context": ""}
        response_mode = detect_chat_response_mode(
            messages,
            last_user_msg,
            web_search_enabled=web_search_enabled,
            research_context="",
        )
        effective_web_search = should_run_web_research(
            last_user_msg,
            response_mode=response_mode,
            requested_enabled=web_search_enabled,
        )

        if effective_web_search and not stream:
            research_llm = get_llm(kind="text")
            research_bundle = run_web_research(
                research_llm,
                messages=messages,
                user_question=last_user_msg,
                temperature=temperature,
                repeat_penalty=repeat_penalty,
                search_level=web_search_level,
            )
            response_mode = detect_chat_response_mode(
                messages,
                last_user_msg,
                web_search_enabled=effective_web_search,
                research_context=research_bundle.get("context", ""),
            )
        log.info(
            "[chat] response_mode=%s web_search=%s requested_web_search=%s has_images=%s pergunta=%r",
            response_mode,
            effective_web_search,
            web_search_enabled,
            has_images,
            last_user_msg,
        )
        answer_temperature = min(temperature, 0.18) if response_mode == "informational" else temperature
        keep_alive = resolve_ollama_keep_alive(cfg)

        if stream:
            def sse(payload):
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            @stream_with_context
            def generate():
                try:
                    local_research = {"items": [], "context": ""}
                    local_response_mode = response_mode
                    local_answer_temperature = answer_temperature

                    if effective_web_search:
                        research_generator = stream_web_research(
                            get_llm(kind="text"),
                            messages=messages,
                            user_question=last_user_msg,
                            temperature=temperature,
                            repeat_penalty=repeat_penalty,
                            search_level=web_search_level,
                        )
                        while True:
                            try:
                                payload = next(research_generator)
                                yield sse(payload)
                            except StopIteration as stop:
                                local_research = stop.value or {"items": [], "context": ""}
                                local_response_mode = detect_chat_response_mode(
                                    messages,
                                    last_user_msg,
                                    web_search_enabled=effective_web_search,
                                    research_context=local_research.get("context", ""),
                                )
                                local_answer_temperature = (
                                    min(temperature, 0.28)
                                    if local_response_mode == "informational"
                                    else temperature
                                )
                                log.info(
                                    "[chat] response_mode=%s web_search=%s requested_web_search=%s has_images=%s pergunta=%r",
                                    local_response_mode,
                                    effective_web_search,
                                    web_search_enabled,
                                    has_images,
                                    last_user_msg,
                                )
                                break

                    yield sse({
                        "type": "research_status",
                        "status": "answering",
                        "message": "Escrevendo resposta final...",
                    })

                    final_messages = build_chat_messages(
                        messages,
                        research_context=local_research.get("context", ""),
                        response_mode=local_response_mode,
                    )
                    yield from stream_llm_completion(
                        get_llm(kind="vision" if has_images else "text"),
                        messages=final_messages,
                        max_tokens=900,
                        temperature=local_answer_temperature,
                        repeat_penalty=repeat_penalty,
                        finalizer=sanitize_llm_text,
                        final_doneizer=normalize_music_chat_reply if local_response_mode == "music" else sanitize_llm_text,
                        keep_alive=keep_alive,
                    )
                except Exception as exc:
                    yield sse({"error": str(exc)})
                finally:
                    if should_unload_text_model(cfg):
                        free_llm()

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        llm = get_llm(kind="vision" if has_images else "text")
        full_messages = build_chat_messages(
            messages,
            research_context=research_bundle.get("context", ""),
            response_mode=response_mode,
        )
        response_text = run_llm_completion(
            llm,
            messages=full_messages,
            max_tokens=800,
            temperature=answer_temperature,
            repeat_penalty=repeat_penalty,
            finalizer=sanitize_llm_text,
            keep_alive=keep_alive,
        ).strip()
        if response_mode == "music":
            response_text = normalize_music_chat_reply(response_text)
        if should_unload_text_model(cfg):
            free_llm()
        return jsonify({
            "success": True,
            "reply": response_text,
            "research": research_bundle.get("items", []),
        })
    except Exception as exc:
        log.exception("Falha no chat Ollama")
        try:
            if should_unload_text_model(load_app_config()):
                free_llm()
        except Exception:
            pass
        return jsonify({"success": False, "error": str(exc)}), 500


def api_chat_legacy_ollama():
    return api_chat_ollama()


def api_set_config_ollama():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Corpo JSON necessario"}), 400

    current = load_app_config()
    merged = dict(current)
    merged.update(data)
    merged.setdefault("llm_model_id", get_default_llm_id("text"))
    merged.setdefault("llm_vision_model_id", get_default_llm_id("vision"))
    save_app_config(merged)
    log.info("Configuracoes salvas com sucesso")

    selected_text = merged.get("llm_model_id")
    selected_vision = merged.get("llm_vision_model_id")
    if current.get("llm_model_id") != selected_text and selected_text in AVAILABLE_LLMS:
        start_model_pull(selected_text)
    if current.get("llm_vision_model_id") != selected_vision and selected_vision in AVAILABLE_LLMS:
        start_model_pull(selected_vision)

    return jsonify({"success": True})


app.view_functions["api_llm_status"] = api_llm_status_ollama
app.view_functions["api_llm_download"] = api_llm_download_ollama
app.view_functions["api_generate_lyrics"] = api_generate_lyrics_ollama
app.view_functions["api_chat"] = api_chat_ollama
app.view_functions["api_chat_legacy"] = api_chat_legacy_ollama
app.view_functions["api_set_config"] = api_set_config_ollama


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    import webbrowser

    threading.Thread(target=run_setup, daemon=True).start()

    log.info(f"🎵 Lyra-Engine em http://localhost:{FLASK_PORT}")

    def open_browser():
        time.sleep(3)
        webbrowser.open(f"http://localhost:{FLASK_PORT}")
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
