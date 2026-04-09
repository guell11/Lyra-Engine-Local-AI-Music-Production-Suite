/* ═══════════════════════════════════════════════════════════
   Lyra-Engine — Frontend Logic (PT-BR)
   Navegacao por abas, Feed, Configuracoes, Prompt IA
   ═══════════════════════════════════════════════════════════ */

const API = "";  // same origin
const BOOT_OVERLAY_SEEN_KEY = "lyra_boot_overlay_seen";

// ── DOM Helpers ──────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const firstOf = (...selectors) => selectors.map((sel) => $(sel)).find(Boolean) || null;
const on = (el, event, handler, options) => {
    if (el) el.addEventListener(event, handler, options);
};

const els = {
    setupOverlay: $("#setup-overlay"),
    setupMessage: $("#setup-message"),
    setupProgress: $("#setup-progress-bar"),
    setupDetail: $("#setup-detail"),
    app: $("#app"),
    // Creation
    captionInput: $("#caption-input"),
    lyricsInput: $("#lyrics-input"),
    lyricsContainer: $("#lyrics-container"),
    toggleLyrics: $("#toggle-lyrics"),
    aiPromptInput: firstOf("#ai-prompt-input", "#prompt-input"),
    languageSelect: firstOf("#language-select", "#opt-language"),
    songTitle: $("#song-title"),
    btnGenerate: $("#btn-generate"),
    btnAiLyrics: $("#btn-ai-lyrics"),
    songList: $("#song-list"),
    emptyState: $("#empty-state"),
    genStatus: $("#generation-status"),
    genTitle: $("#gen-title"),
    genCaption: $("#gen-caption"),
    searchSongs: $("#search-songs"),
    // Advanced
    advancedSection: firstOf("#advanced-section", ".advanced-only"),
    optDuration: $("#opt-duration"),
    optBpm: $("#opt-bpm"),
    optKey: $("#opt-key"),
    optTime: $("#opt-time"),
    optSteps: $("#opt-steps"),
    optStepsVal: $("#opt-steps-val"),
    optShift: $("#opt-shift"),
    optShiftVal: $("#opt-shift-val"),
    optCfg: $("#opt-cfg"),
    optCfgVal: $("#opt-cfg-val"),
    optBatch: $("#opt-batch"),
    optSeed: $("#opt-seed"),
    voiceSelect: firstOf("#voice-select", "#voice-preset"),
    voiceUpload: firstOf("#voice-upload-input", "#audio-file"),
    btnUploadAudio: $("#btn-upload-audio"),
    // Mode
    btnModeSimple: $("#btn-mode-simple"),
    btnModeAdvanced: $("#btn-mode-advanced"),
    // Pages
    pageCriar: $("#page-criar"),
    pageFeed: $("#page-feed"),
    pageConfig: $("#page-config"),
    pageChat: $("#page-chat"),
    tabCriar: $("#tab-criar"),
    tabFeed: $("#tab-feed"),
    tabConfig: $("#tab-config"),
    tabChat: $("#tab-chat"),
    configTheme: $("#config-theme"),
    configDefaultLang: $("#config-default-lang"),
    configDefaultDuration: $("#config-default-duration"),
    configDefaultSteps: $("#config-default-steps"),
    configLlmTemperature: $("#config-llm-temperature"),
    valTemp: $("#val-temp"),
    configLlmPenalty: $("#config-llm-penalty"),
    valPen: $("#val-pen"),
    configAcestepVram: $("#config-acestep-vram"),
    configGemmaVram: $("#config-gemma-vram"),
    infoLlm: $("#info-llm"),
    llmModelsContainer: $("#llm-models-container"),
    feedGrid: $("#feed-grid"),
    feedEmpty: $("#feed-empty"),
    feedSearch: $("#feed-search"),
    feedSort: $("#feed-sort"),
    // Settings
    configBasePrompt: $("#config-base-prompt"),
    configMaxTokens: $("#config-max-tokens"),
    configDefaultLang: $("#config-default-lang"),
    configDefaultDuration: $("#config-default-duration"),
    configDefaultSteps: $("#config-default-steps"),
    configAcestepVram: $("#config-acestep-vram"),
    configGemmaVram: $("#config-gemma-vram"),
    btnReloadEngines: $("#btn-reload-engines"),
    reloadMsg: $("#reload-msg"),
    btnSaveSettings: $("#btn-save-settings"),
    infoStatus: $("#info-status"),
    infoGpu: $("#info-gpu"),
    infoLlm: $("#info-llm"),
    // Player
    audio: $("#audio-player"),
    btnPlay: $("#btn-play"),
    btnPrev: $("#btn-prev"),
    btnNext: $("#btn-next"),
    playIcon: $("#play-icon"),
    pauseIcon: $("#pause-icon"),
    playerTitle: $("#player-title"),
    playerCaption: $("#player-caption"),
    timeCurrent: $("#time-current"),
    timeTotal: $("#time-total"),
    progressTrack: $("#progress-track"),
    progressFill: $("#progress-fill"),
    progressThumb: $("#progress-thumb"),
    volumeSlider: $("#volume-slider"),
    serverStatus: $("#server-status"),
};

// ── State ─────────────────────────────────────────────────
let songs = [];
let currentSongIndex = -1;
let isGenerating = false;
let isGeneratingLyrics = false;
let selectedStyles = [];
let serverReady = false;
let currentMode = "simple"; // "simple" or "advanced"
const PAGE_ROUTE_MAP = {
    criar: "/",
    feed: "/feed",
    config: "/configuracoes",
    chat: "/chat",
};

let currentPage = document.body?.dataset?.activePage || "criar";
let autosaveTimer = null;
let lastSavedConfigSnapshot = "";
let appConfig = {
    theme: "dark",
    llm_temperature: 1.05,
    llm_repeat_penalty: 1.1,
    llm_model_id: "gaia_text_4b",
    llm_vision_model_id: "gaia_vision_4b",
    basePrompt: "",
    maxTokens: 1024,
    defaultLang: "pt",
    defaultDuration: 90,
    defaultSteps: 25,
    acestep_vram_mode: "vram",
    gemma_vram_mode: "ram",
};

function normalizeRetentionMode(value, fallback = "ram") {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "auto" || normalized === "vram" || normalized === "ram" || normalized === "unload") {
        return normalized;
    }
    return fallback;
}

// ══════════════════════════════════════════════════════════
//  SETUP POLLING
// ══════════════════════════════════════════════════════════

function hasSeenBootOverlay() {
    try {
        return sessionStorage.getItem(BOOT_OVERLAY_SEEN_KEY) === "1";
    } catch {
        return false;
    }
}

function markBootOverlaySeen() {
    try {
        sessionStorage.setItem(BOOT_OVERLAY_SEEN_KEY, "1");
    } catch {
        // ignore
    }
}

function clearBootOverlaySeen() {
    try {
        sessionStorage.removeItem(BOOT_OVERLAY_SEEN_KEY);
        delete document.documentElement.dataset.bootOverlaySeen;
    } catch {
        // ignore
    }
}

function showSetupOverlay() {
    els.setupOverlay?.classList.remove("hidden");
}

function hideSetupOverlay() {
    els.setupOverlay?.classList.add("hidden");
}

function setSetupProgress(pct, msg, detail) {
    if (els.setupProgress) els.setupProgress.style.width = pct + "%";
    if (msg && els.setupMessage) els.setupMessage.textContent = msg;
    if (detail && els.setupDetail) els.setupDetail.textContent = detail;
}

function markServerReady(mode = "online") {
    clearBootOverlaySeen();
    hideSetupOverlay();
    serverReady = true;
    if (els.btnGenerate) els.btnGenerate.disabled = false;
    updateServerStatus("online");
    if (els.infoStatus) {
        els.infoStatus.textContent = mode === "standby" ? "Pronto sob demanda" : "Online";
    }
    loadSongs();
    loadConfig();
}

async function pollSetup(options = {}) {
    // ── F5 FIX: se o servidor ja esta online, pula o setup ──
    const { silent = false } = options;
    const setProgress = (pct, msg, detail) => {
        if (!silent) {
            setSetupProgress(pct, msg, detail);
        }
    };

    while (true) {
        try {
            const res = await fetch(`${API}/api/setup-status`);
            const data = await res.json();

            if (data.complete || data.phase === "standby") {
                const standbyMode = data.phase === "standby";
                setProgress(
                    100,
                    standbyMode ? "Pronto sob demanda!" : "Pronto!",
                    standbyMode ? "Motor de musica sera carregado automaticamente ao gerar." : "Iniciando Lyra-Engine..."
                );
                await sleep(standbyMode ? 250 : 600);
                markServerReady(standbyMode ? "standby" : "online");
                return;
            }

            if (data.error) {
                setProgress(0, "Erro no Setup", data.error);
                if (els.setupProgress) els.setupProgress.style.background = "#ef4444";
                updateServerStatus("offline");
                return;
            }

            const phases = { setup: 30, loading: 70, starting: 90 };
            const basePct = phases[data.phase] || 10;
            const stepPct = data.total > 0 ? (data.current / data.total) * 20 : 0;
            setProgress(basePct + stepPct, data.message, `Fase: ${data.phase}`);
            updateServerStatus("connecting");

        } catch (e) {
            updateServerStatus("offline");
        }
        await sleep(1500);
    }
}

function initializeAppShell() {
    loadSongs();
    loadConfig();
    loadVoices();
    fetchLlmStatus();
}

async function initializeBootState() {
    const bootComplete = document.body.dataset.bootComplete === "true";
    const bootPhase = document.body.dataset.bootPhase || "idle";
    const shouldShowOverlay = !bootComplete && !hasSeenBootOverlay();

    if (bootComplete) {
        markServerReady();
        return;
    }

    serverReady = false;
    if (els.btnGenerate) els.btnGenerate.disabled = true;

    if (shouldShowOverlay) {
        markBootOverlaySeen();
        showSetupOverlay();
        setSetupProgress(12, els.setupMessage?.textContent || "Inicializando...", `Fase: ${bootPhase}`);
        await pollSetup({ silent: false });
        return;
    }

    hideSetupOverlay();
    updateServerStatus("connecting");
    pollSetup({ silent: true });
}

// ══════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════
function resolvePageFromLocation(pathname = window.location.pathname) {
    if (pathname === "/feed") return "feed";
    if (pathname === "/configuracoes") return "config";
    if (pathname === "/chat") return "chat";
    return "criar";
}

function navigateTo(page, options = {}) {
    const normalizedPage = PAGE_ROUTE_MAP[page] ? page : "criar";
    const pageEl = document.getElementById(`page-${normalizedPage}`);
    if (!pageEl) return;

    const shouldUpdateHistory = options.updateHistory !== false;
    const shouldReplaceHistory = options.replaceHistory === true;

    currentPage = normalizedPage;
    document.body.dataset.activePage = normalizedPage;

    $$(".nav-tab[data-page]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.page === normalizedPage);
    });

    $$("#page-criar, #page-feed, #page-config, #page-chat").forEach((node) => {
        node.classList.toggle("active", node.id === `page-${normalizedPage}`);
    });

    if (shouldUpdateHistory) {
        const targetRoute = PAGE_ROUTE_MAP[normalizedPage] || "/";
        if (window.location.pathname !== targetRoute) {
            const method = shouldReplaceHistory ? "replaceState" : "pushState";
            window.history[method]({ page: normalizedPage }, "", targetRoute);
        }
    }

    if (normalizedPage === "feed") {
        renderFeed();
    }

    if (normalizedPage === "chat") {
        setTimeout(() => {
            document.getElementById("chat-input")?.focus();
        }, 30);
    }

    window.dispatchEvent(new CustomEvent("lyra:navigate", {
        detail: {
            page: normalizedPage,
            route: PAGE_ROUTE_MAP[normalizedPage] || "/",
        },
    }));
}

document.addEventListener("click", (event) => {
    const tab = event.target.closest(".nav-tab[data-page]");
    if (!tab) return;
    if (event.defaultPrevented) return;
    if (event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigateTo(tab.dataset.page);
}, true);

window.addEventListener("popstate", () => {
    navigateTo(resolvePageFromLocation(), { updateHistory: false });
});

window.navigateLyraPage = (page, options = {}) => navigateTo(page, options);

    async function fetchLlmStatus() {
        const container = document.getElementById("llm-models-container");
        const infoLlm = document.getElementById("info-llm");
        const chatModelBadge = document.getElementById("chat-model-selector");
        if (!container) return;

        try {
            const res = await fetch(`${API}/api/llm/status`);
            if (!res.ok) return;

            const data = await res.json();
            container.innerHTML = "";
            let anyDownloading = false;

            if (infoLlm) {
                if (data.runtime_error) {
                    infoLlm.textContent = "Ollama offline";
                    infoLlm.title = data.runtime_error;
                } else {
                    infoLlm.textContent = data.engine_label || "Ollama online";
                    infoLlm.title = data.notice || "";
                }
            }

            for (const [mId, mInfo] of Object.entries(data.models)) {
                if (mInfo.status === "downloading") anyDownloading = true;

                const card = document.createElement("div");
                card.className = `llm-model-card${mInfo.selected ? " active" : ""}`;

                let btnHtml = "";
                if (mInfo.status === "ready" || mInfo.status === "downloaded") {
                    if (mInfo.selected) {
                        btnHtml = `<button class="llm-model-card-btn btn-selected" disabled>Ativo</button>`;
                        if (chatModelBadge) {
                            chatModelBadge.innerHTML = `${escHtml(mInfo.title)} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`;
                        }
                    } else {
                        btnHtml = `<button class="llm-model-card-btn btn-select" onclick="selectModel('${mId}')">Selecionar</button>`;
                    }
                } else if (mInfo.status === "downloading") {
                    btnHtml = `<span style="font-size:0.78rem;color:#f59e0b;">${escHtml(mInfo.progress || "Preparando...")}</span>`;
                } else {
                    btnHtml = `<button class="llm-model-card-btn btn-download" onclick="downloadLLM('${mId}')">Instalar</button>`;
                }

                card.innerHTML = `
                    <div class="llm-model-card-info">
                        <div class="llm-model-card-name">${escHtml(mInfo.title)}</div>
                        <div class="llm-model-card-size">${escHtml(mInfo.description || mInfo.size)}${mInfo.progress ? ` · ${escHtml(mInfo.progress)}` : ""}</div>
                    </div>
                    ${btnHtml}
                `;
                container.appendChild(card);
            }

            if (anyDownloading) setTimeout(fetchLlmStatus, 2000);
        } catch (e) {
            if (infoLlm) {
                infoLlm.textContent = "Ollama indisponivel";
                infoLlm.title = e.message || "Falha ao consultar status.";
            }
        }
    }

    window.selectModel = async function(modelId) {
        appConfig.llm_model_id = modelId;
        await performAutoSave(false);
        window.downloadLLM(modelId, false);
        fetchLlmStatus();
    };

    window.downloadLLM = async function(modelId, notify = true) {
        appConfig.llm_model_id = modelId;
        await performAutoSave(false);
        if (notify) showToast("Preparando modelo no Ollama...", "info");
        try {
            const res = await fetch(`${API}/api/llm/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: modelId })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.error || "Falha ao preparar modelo no Ollama.");
            }
            fetchLlmStatus();
        } catch (e) {
            showToast(e.message || "Erro ao requisitar modelo", "error");
        }
    };

// ══════════════════════════════════════════════════════════
//  MODE TOGGLE (Simple / Advanced)
// ══════════════════════════════════════════════════════════
function setMode(mode) {
    currentMode = mode;
    els.btnModeSimple?.classList.toggle("active", mode === "simple");
    els.btnModeAdvanced?.classList.toggle("active", mode === "advanced");
    els.advancedSection?.classList.toggle("hidden", mode === "simple");
}

on(els.btnModeSimple, "click", () => setMode("simple"));
on(els.btnModeAdvanced, "click", () => setMode("advanced"));

// ══════════════════════════════════════════════════════════
//  STYLE TAGS
// ══════════════════════════════════════════════════════════
$$(".style-pill").forEach(btn => {
    btn.addEventListener("click", () => {
        const style = btn.dataset.style;
        btn.classList.toggle("active");
        if (btn.classList.contains("active")) {
            selectedStyles.push(style);
        } else {
            selectedStyles = selectedStyles.filter(s => s !== style);
        }
        updateCaptionFromStyles();
    });
});

function updateCaptionFromStyles() {
    const current = els.captionInput.value;
    if (!current || current.startsWith(">> ")) {
        els.captionInput.value = selectedStyles.length > 0
            ? ">> " + selectedStyles.join(", ")
            : "";
    }
}

// ══════════════════════════════════════════════════════════
//  LYRICS TAGS
// ══════════════════════════════════════════════════════════
const LYRICS_STRUCTURE_TEMPLATES = {
    short: "[Intro]\n\n[Verse 1]\n\n[Chorus]\n\n[Verse 2]\n\n[Chorus]\n\n[Outro]",
    standard: "[Intro]\n\n[Verse 1]\n\n[Pre-Chorus]\n\n[Chorus]\n\n[Verse 2]\n\n[Pre-Chorus]\n\n[Chorus]\n\n[Bridge]\n\n[Final Chorus]\n\n[Outro]",
    long: "[Intro]\n\n[Verse 1]\n\n[Pre-Chorus]\n\n[Chorus]\n\n[Verse 2]\n\n[Pre-Chorus]\n\n[Chorus]\n\n[Verse 3]\n\n[Bridge]\n\n[Hook]\n\n[Final Chorus]\n\n[Outro]",
};

function syncLanguagePills() {
    const selected = els.languageSelect?.value || appConfig.defaultLang || "pt";
    $$(".language-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.dataset.lang === selected);
    });
}

function syncDurationPills() {
    const selected = String(parseInt(els.optDuration?.value, 10) || appConfig.defaultDuration || 90);
    $$(".duration-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.dataset.duration === selected);
    });
}

$$(".tag-btn, .lyric-tag").forEach(btn => {
    btn.addEventListener("click", () => {
        const textarea = els.lyricsInput;
        if (!textarea) return;

        if (btn.classList.contains("structure-btn")) {
            const template = LYRICS_STRUCTURE_TEMPLATES[btn.dataset.structure];
            if (!template) return;
            textarea.value = template;
            textarea.focus();
            textarea.selectionStart = textarea.value.length;
            textarea.selectionEnd = textarea.value.length;
            return;
        }

        const tag = btn.dataset.tag || btn.textContent.trim();
        if (!tag) return;
        const start = textarea.selectionStart;
        const val = textarea.value;
        const insert = (start > 0 && val[start - 1] !== "\n" ? "\n" : "") + tag + "\n";
        textarea.value = val.substring(0, start) + insert + val.substring(start);
        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = start + insert.length;
    });
});

$$(".language-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
        if (!els.languageSelect) return;
        els.languageSelect.value = pill.dataset.lang || "pt";
        syncLanguagePills();
    });
});

$$(".duration-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
        if (!els.optDuration) return;
        els.optDuration.value = pill.dataset.duration || "60";
        syncDurationPills();
    });
});

// ══════════════════════════════════════════════════════════
//  AI LYRICS GENERATION (Gemma 2B GGUF)
// ══════════════════════════════════════════════════════════
on(els.btnAiLyrics, "click", handleGenerateLyrics);

async function handleGenerateLyrics() {
    if (isGeneratingLyrics || !els.lyricsInput) return;

    const genre = els.captionInput.value.trim() || selectedStyles.join(", ") || "pop";
    const language = els.languageSelect?.value || appConfig.defaultLang || "pt";
    const userPrompt = (els.aiPromptInput?.value || "").trim();
    const requestedDuration = parseInt(els.optDuration?.value, 10) || 90;

    // Map language codes to full names
    const langNames = {
        en: "English", pt: "Portuguese", es: "Spanish", fr: "French",
        de: "German", it: "Italian", ja: "Japanese", ko: "Korean"
    };
    const langName = langNames[language] || "Portuguese";

    isGeneratingLyrics = true;
    els.btnAiLyrics.classList.add("generating");
    els.btnAiLyrics.querySelector("span").textContent = "Gerando ao vivo...";

    // Enable lyrics if disabled
    if (!els.toggleLyrics.checked) {
        els.toggleLyrics.checked = true;
        els.lyricsContainer?.classList.remove("hidden");
    }

    // Clear and show typing indicator
    els.lyricsInput.value = "";
    els.lyricsInput.placeholder = "IA esta escrevendo letras...";
    els.lyricsContainer?.classList.add("lyrics-generating");

    try {
        const res = await fetch(`${API}/api/generate-lyrics`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                genre,
                language: langName,
                prompt: userPrompt,
                base_prompt: appConfig.basePrompt,
                stream: true,
                max_tokens: Math.max(
                    appConfig.maxTokens || 1024,
                    requestedDuration >= 180 ? 1400 :
                    requestedDuration >= 120 ? 1100 :
                    requestedDuration >= 90 ? 900 : 700
                ),
                temperature: appConfig.llm_temperature,
                duration: requestedDuration,
            }),
        });

        const contentType = String(res.headers.get("content-type") || "").toLowerCase();

        if (!contentType.includes("text/event-stream")) {
            const data = await res.json();

            if (data.error) {
                showToast(data.error, "error");
                els.lyricsInput.placeholder = "Escreva suas letras aqui... Use tags como [Verse], [Chorus], [Bridge], [Hook] e [Final Chorus]";
                els.lyricsContainer?.classList.remove("lyrics-generating");
                return;
            }

            if (data.lyrics) {
                await typewriterEffect(els.lyricsInput, data.lyrics);
                showToast("Letras geradas com sucesso pela IA!", "success");
            }
        } else {
            let streamError = null;
            let streamedLyrics = "";

            await readSseResponse(res, (event) => {
                if (event.error) {
                    streamError = event.error;
                    return;
                }

                streamedLyrics = typeof event.text === "string"
                    ? event.text
                    : streamedLyrics + (event.delta || "");
                els.lyricsInput.value = streamedLyrics;
                els.lyricsInput.scrollTop = els.lyricsInput.scrollHeight;
            });

            if (streamError) {
                throw new Error(streamError);
            }

            if (streamedLyrics.trim()) {
                els.lyricsInput.value = streamedLyrics.trim();
                showToast("Letras geradas com stream em tempo real!", "success");
            }
        }
    } catch (e) {
        showToast("Falha ao gerar letras: " + e.message, "error");
    } finally {
        isGeneratingLyrics = false;
        els.btnAiLyrics.classList.remove("generating");
        els.btnAiLyrics.querySelector("span").textContent = "Gerar com IA";
        els.lyricsInput.placeholder = "Escreva suas letras aqui... Use tags como [Verse], [Chorus], [Bridge], [Hook] e [Final Chorus]";
        els.lyricsContainer?.classList.remove("lyrics-generating");
    }
}

async function typewriterEffect(textarea, text) {
    textarea.value = "";
    const chars = text.split("");
    let i = 0;
    while (i < chars.length) {
        // Processa 3 chars por vez para ser mais rapido
        const chunk = chars.slice(i, i + 3).join("");
        textarea.value += chunk;
        textarea.scrollTop = textarea.scrollHeight;
        i += 3;
        const delay = chunk.includes("\n") ? 15 : 5;
        await sleep(delay);
    }
}

// ══════════════════════════════════════════════════════════
//  TOGGLE SECTIONS
// ══════════════════════════════════════════════════════════
async function readSseResponse(response, onEvent) {
    if (!response.body) {
        throw new Error("Streaming nao disponivel neste navegador.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
            const rawEvent = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const payload = rawEvent
                .split(/\r?\n/)
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trimStart())
                .join("\n");

            if (payload) {
                try {
                    onEvent(JSON.parse(payload));
                } catch (_error) {
                    onEvent({ error: "Resposta do stream em formato invalido." });
                }
            }

            boundary = buffer.indexOf("\n\n");
        }

        if (done) break;
    }
}

on(els.toggleLyrics, "change", () => {
    els.lyricsContainer?.classList.toggle("hidden", !els.toggleLyrics.checked);
});
on(els.languageSelect, "change", syncLanguagePills);
on(els.optDuration, "input", syncDurationPills);

// Range sliders
on(els.optSteps, "input", () => {
    if (els.optStepsVal) els.optStepsVal.textContent = els.optSteps.value;
});
on(els.optShift, "input", () => {
    if (els.optShiftVal) els.optShiftVal.textContent = parseFloat(els.optShift.value).toFixed(1);
});
on(els.optCfg, "input", () => {
    if (els.optCfgVal) els.optCfgVal.textContent = parseFloat(els.optCfg.value).toFixed(1);
});

// ══════════════════════════════════════════════════════════
//  GENERATE MUSIC
// ══════════════════════════════════════════════════════════
on(els.btnGenerate, "click", handleGenerate);

async function handleGenerate() {
    if (isGenerating || !serverReady || !els.captionInput) return;

    const caption = els.captionInput.value.trim();
    if (!caption) {
        showToast("Descreva o estilo da sua musica.", "error");
        els.captionInput.focus();
        return;
    }

    isGenerating = true;
    els.btnGenerate.classList.add("generating");
    els.btnGenerate.querySelector("span").textContent = "Gerando...";
    els.btnGenerate.disabled = true;

    const title = els.songTitle.value.trim() || "Musica Sem Titulo";
    els.genTitle.textContent = title;
    els.genCaption.textContent = caption;
    els.genStatus.classList.remove("hidden");

    const payload = {
        caption: caption,
        title: title,
        vocal_language: els.languageSelect?.value || appConfig.defaultLang || "pt",
        duration: parseInt(els.optDuration?.value) || 90,
        inference_steps: parseInt(els.optSteps?.value) || 25,
        cfg_scale: parseFloat(els.optCfg?.value) || 10.0,
        shift: parseFloat(els.optShift?.value) || 4.0,
        batch_size: parseInt(els.optBatch?.value) || 1,
        seed: parseInt(els.optSeed?.value) || -1,
        time_signature: els.optTime?.value || "",
        ui_mode: currentMode,
        cot: true,
    };

    // Adiciona referencia vocal se selecionada
    if (els.voiceSelect?.value) {
        payload.reference_audio = els.voiceSelect.value;
    }



    if (els.toggleLyrics.checked && els.lyricsInput.value.trim()) {
        payload.lyrics = els.lyricsInput.value.trim();
    }
    if (els.optBpm?.value) payload.bpm = parseInt(els.optBpm.value);
    if (els.optKey?.value) payload.key_scale = els.optKey.value;

    try {
        const res = await fetch(`${API}/api/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (data.success) {
            if (Array.isArray(data.tuning_notes) && data.tuning_notes.length) {
                showToast(data.tuning_notes[0], "info");
            }
            showToast("Musica gerada com sucesso!", "success");
            await loadSongs();
            if (songs.length > 0) {
                playSong(0);
            }
        } else {
            showToast(data.error || "Falha na geracao.", "error");
        }
    } catch (e) {
        showToast("Erro de conexao: " + e.message, "error");
    } finally {
        isGenerating = false;
        els.btnGenerate.classList.remove("generating");
        els.btnGenerate.querySelector("span").textContent = "Criar Musica";
        els.btnGenerate.disabled = false;
        els.genStatus.classList.add("hidden");
    }
}

// ══════════════════════════════════════════════════════════
//  SONG LIST (Workspace)
// ══════════════════════════════════════════════════════════
async function loadSongs() {
    try {
        const res = await fetch(`${API}/api/songs`);
        songs = await res.json();
        if (els.songList) renderSongs();
        if (els.feedGrid) renderFeed();
    } catch (e) {
        console.error("Falha ao carregar musicas:", e);
    }
}

function renderSongs(filter = "") {
    if (!els.songList || !els.emptyState) return;
    const filtered = filter
        ? songs.filter(s =>
            (s.title || "").toLowerCase().includes(filter) ||
            (s.caption || "").toLowerCase().includes(filter)
        )
        : songs;

    if (filtered.length === 0) {
        els.emptyState.classList.remove("hidden");
        els.songList.querySelectorAll(".song-card").forEach(c => c.remove());
        return;
    }

    els.emptyState.classList.add("hidden");
    els.songList.querySelectorAll(".song-card").forEach(c => c.remove());

    filtered.forEach((song, i) => {
        const card = document.createElement("div");
        card.className = "song-card" + (i === currentSongIndex ? " playing" : "");
        card.innerHTML = `
            <div class="song-art">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                <div class="play-overlay">
                    <svg viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                </div>
            </div>
            <div class="song-details">
                <h4>${escHtml(song.title || "Sem Titulo")}</h4>
                <p>${escHtml(song.caption || "---")}</p>
            </div>
            <div class="song-meta">
                <span>${song.duration ? song.duration + "s" : ""}</span>
                <span>${song.size_mb ? song.size_mb + " MB" : ""}</span>
            </div>
            <div class="song-actions">
                <button class="song-action-btn extend" title="Estender" data-file="${escAttr(song.filename)}" data-caption="${escAttr(song.caption || '')}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/><line x1="19" y1="19" x2="23" y2="23"/></svg>
                </button>
                <button class="song-action-btn download" title="Baixar" data-file="${escAttr(song.filename)}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
                <button class="song-action-btn delete" title="Deletar" data-file="${escAttr(song.filename)}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
            </div>
        `;

        card.addEventListener("click", (e) => {
            if (e.target.closest(".song-action-btn")) return;
            const idx = songs.indexOf(song);
            playSong(idx);
        });

        card.querySelector(".extend").addEventListener("click", () => {
            extendSong(song.filename, song.caption || "");
        });

        card.querySelector(".download").addEventListener("click", () => {
            const a = document.createElement("a");
            a.href = `${API}/api/songs/${song.filename}`;
            a.download = song.filename;
            a.click();
        });

        card.querySelector(".delete").addEventListener("click", async () => {
            if (!confirm(`Deletar "${song.title}"?`)) return;
            await fetch(`${API}/api/songs/${song.filename}`, { method: "DELETE" });
            await loadSongs();
            showToast("Musica deletada.", "success");
        });

        els.songList.appendChild(card);
    });
}

on(els.searchSongs, "input", () => {
    renderSongs((els.searchSongs?.value || "").toLowerCase());
});

// ══════════════════════════════════════════════════════════
//  FEED PAGE
// ══════════════════════════════════════════════════════════
function renderFeed() {
    if (!els.feedGrid || !els.feedEmpty) return;
    const search = (els.feedSearch?.value || "").toLowerCase();
    const sortBy = els.feedSort?.value || "newest";

    let filtered = search
        ? songs.filter(s =>
            (s.title || "").toLowerCase().includes(search) ||
            (s.caption || "").toLowerCase().includes(search)
        )
        : [...songs];

    // Sort
    switch (sortBy) {
        case "oldest":
            filtered.reverse();
            break;
        case "name":
            filtered.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
            break;
        case "size":
            filtered.sort((a, b) => (b.size_mb || 0) - (a.size_mb || 0));
            break;
        // "newest" is default order
    }

    // Clear
    els.feedGrid.querySelectorAll(".feed-card").forEach(c => c.remove());

    if (filtered.length === 0) {
        els.feedEmpty.classList.remove("hidden");
        return;
    }
    els.feedEmpty.classList.add("hidden");

    filtered.forEach((song, i) => {
        const card = document.createElement("div");
        card.className = "feed-card" + (i === currentSongIndex ? " playing" : "");
        card.innerHTML = `
            <div class="feed-card-art">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                <div class="feed-play-overlay">
                    <svg viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                </div>
            </div>
            <div class="feed-card-info">
                <h4>${escHtml(song.title || "Sem Titulo")}</h4>
                <p>${escHtml(song.caption || "---")}</p>
            </div>
            <div class="feed-card-meta">
                <span>${song.duration ? song.duration + "s" : ""} ${song.size_mb ? "| " + song.size_mb + " MB" : ""}</span>
                <div class="feed-card-actions">
                    <button class="song-action-btn download" title="Baixar">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    </button>
                    <button class="song-action-btn delete" title="Deletar">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            </div>
        `;

        card.addEventListener("click", (e) => {
            if (e.target.closest(".song-action-btn")) return;
            const idx = songs.indexOf(song);
            playSong(idx);
        });

        card.querySelector(".download").addEventListener("click", (e) => {
            e.stopPropagation();
            const a = document.createElement("a");
            a.href = `${API}/api/songs/${song.filename}`;
            a.download = song.filename;
            a.click();
        });

        card.querySelector(".delete").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (!confirm(`Deletar "${song.title}"?`)) return;
            await fetch(`${API}/api/songs/${song.filename}`, { method: "DELETE" });
            await loadSongs();
            renderFeed();
            showToast("Musica deletada.", "success");
        });

        els.feedGrid.appendChild(card);
    });
}

on(els.feedSearch, "input", renderFeed);
on(els.feedSort, "change", renderFeed);

// ══════════════════════════════════════════════════════════
//  SETTINGS / CONFIG
// ══════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
//  SETTINGS / CONFIG (AUTO-SAVE)
// ══════════════════════════════════════════════════════════
async function loadConfig() {
    try {
        const res = await fetch(`${API}/api/config`);
        if (res.ok) {
            const data = await res.json();
            Object.assign(appConfig, data);
            appConfig.acestep_vram_mode = normalizeRetentionMode(appConfig.acestep_vram_mode, "vram");
            appConfig.gemma_vram_mode = normalizeRetentionMode(appConfig.gemma_vram_mode, "ram");

            if (els.configTheme && appConfig.theme) els.configTheme.value = appConfig.theme;
            if (els.configDefaultLang && appConfig.defaultLang) els.configDefaultLang.value = appConfig.defaultLang;
            if (els.configDefaultDuration && appConfig.defaultDuration) els.configDefaultDuration.value = appConfig.defaultDuration;
            if (els.configDefaultSteps && appConfig.defaultSteps) els.configDefaultSteps.value = appConfig.defaultSteps;
            if (els.configBasePrompt) els.configBasePrompt.value = appConfig.basePrompt || "";
            if (els.configMaxTokens) els.configMaxTokens.value = appConfig.maxTokens || 1024;
            
            if (els.configLlmTemperature && appConfig.llm_temperature != null) {
                els.configLlmTemperature.value = appConfig.llm_temperature;
                if (els.valTemp) els.valTemp.textContent = parseFloat(appConfig.llm_temperature).toFixed(2);
            }
            if (els.configLlmPenalty && appConfig.llm_repeat_penalty != null) {
                els.configLlmPenalty.value = appConfig.llm_repeat_penalty;
                if (els.valPen) els.valPen.textContent = parseFloat(appConfig.llm_repeat_penalty).toFixed(2);
            }
            if (els.configAcestepVram) els.configAcestepVram.value = appConfig.acestep_vram_mode;
            if (els.configGemmaVram) els.configGemmaVram.value = appConfig.gemma_vram_mode;

            applyTheme(appConfig.theme);

            if (els.languageSelect) els.languageSelect.value = appConfig.defaultLang || "pt";
            if (els.optDuration) els.optDuration.value = appConfig.defaultDuration || 90;
            if (els.optSteps) els.optSteps.value = appConfig.defaultSteps || 25;
            if (els.optStepsVal) els.optStepsVal.textContent = appConfig.defaultSteps || 25;
            if (els.optCfg) els.optCfg.value = "10.0";
            if (els.optCfgVal) els.optCfgVal.textContent = "10.0";
            if (els.optShift) els.optShift.value = "4.0";
            if (els.optShiftVal) els.optShiftVal.textContent = "4.0";
            syncLanguagePills();
            syncDurationPills();
            lastSavedConfigSnapshot = JSON.stringify(appConfig);
        }
    } catch (e) {
        console.log("Configs nao carregadas (usando padrao)", e);
    }
}

function syncConfigFromUI() {
    if (els.configTheme) appConfig.theme = els.configTheme.value;
    if (els.configDefaultLang) appConfig.defaultLang = els.configDefaultLang.value;
    if (els.configDefaultDuration) appConfig.defaultDuration = parseInt(els.configDefaultDuration.value) || 90;
    if (els.configDefaultSteps) appConfig.defaultSteps = parseInt(els.configDefaultSteps.value) || 25;
    if (els.configLlmTemperature) appConfig.llm_temperature = parseFloat(els.configLlmTemperature.value) || 1.05;
    if (els.configLlmPenalty) appConfig.llm_repeat_penalty = parseFloat(els.configLlmPenalty.value) || 1.1;
    if (els.configAcestepVram) appConfig.acestep_vram_mode = normalizeRetentionMode(els.configAcestepVram.value, "vram");
    if (els.configGemmaVram) appConfig.gemma_vram_mode = normalizeRetentionMode(els.configGemmaVram.value, "ram");
    if (els.configBasePrompt) appConfig.basePrompt = els.configBasePrompt.value.trim();
    if (els.configMaxTokens) appConfig.maxTokens = parseInt(els.configMaxTokens.value) || 1024;
}

async function persistConfigIfNeeded() {
    const snapshot = JSON.stringify(appConfig);
    if (snapshot === lastSavedConfigSnapshot) return;
    await fetch(`${API}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(appConfig),
    });
    lastSavedConfigSnapshot = snapshot;
}

async function performAutoSave(reloadPrompt = false) {
    syncConfigFromUI();
    if (reloadPrompt) {
        let conf = confirm("Essa modificacao altera a politica de memoria dos motores de IA e requer reload dos motores.\n\nDeseja reiniciar agora?");
        if (conf) {
            if (els.reloadMsg) els.reloadMsg.style.display = "block";
            try {
                await persistConfigIfNeeded();
                await fetch(`${API}/api/reload-engines`, { method: "POST" });
                showToast("Reiniciando motores...", "info");
                setTimeout(() => window.location.reload(), 1500);
                return;
            } catch(e) { showToast("Falha no reload", "error"); }
        } else {
            showToast("Mudanca salva. Vai entrar no proximo reload dos motores.", "info");
        }
    }

    applyTheme(appConfig.theme);

    if (els.languageSelect) els.languageSelect.value = appConfig.defaultLang;
    if (els.optDuration) els.optDuration.value = appConfig.defaultDuration;
    if (els.optSteps) els.optSteps.value = appConfig.defaultSteps;
    if (els.optStepsVal) els.optStepsVal.textContent = appConfig.defaultSteps;
    syncLanguagePills();
    syncDurationPills();

    try {
        await persistConfigIfNeeded();
    } catch (e) {
        console.warn("Erro ao auto-salvar", e);
    }
}

// Attach Autosave to all inputs
document.querySelectorAll(".autosave").forEach(input => {
    input.addEventListener("change", (e) => {
        if (e.target.classList.contains("vram-trigger")) {
            performAutoSave(true);
        } else {
            performAutoSave(false);
        }
    });
    if (!input.classList.contains("vram-trigger")) {
        input.addEventListener("input", () => {
            clearTimeout(autosaveTimer);
            autosaveTimer = setTimeout(() => performAutoSave(false), 250);
        });
    }
});

on(els.configLlmTemperature, "input", (e) => {
    if (els.valTemp) els.valTemp.textContent = parseFloat(e.target.value).toFixed(2);
});
on(els.configLlmPenalty, "input", (e) => {
    if (els.valPen) els.valPen.textContent = parseFloat(e.target.value).toFixed(2);
});

// ══════════════════════════════════════════════════════════
//  LLM MODELS MANAGEMENT
// ══════════════════════════════════════════════════════════
async function fetchLlmStatus() {
    const container = document.getElementById("llm-models-container");
    const infoLlm = document.getElementById("info-llm");
    if (!container) return;
    try {
        const res = await fetch(`${API}/api/llm/status`);
        if(res.ok) {
            const data = await res.json();
            container.innerHTML = "";
            let anyDownloading = false;
            if (data.runtime_error && infoLlm) {
                infoLlm.textContent = "Erro no LLM";
                infoLlm.title = data.runtime_error;
            } else if (data.notice && infoLlm) {
                infoLlm.textContent = "LLM com fallback";
                infoLlm.title = data.notice;
            }

            for (const [mId, mInfo] of Object.entries(data.models)) {
                if (mInfo.status === "downloading") anyDownloading = true;

                const card = document.createElement("div");
                card.className = `llm-model-card${mInfo.selected ? ' active' : ''}`;

                let btnHtml = "";
                if (mInfo.supported === false) {
                    btnHtml = `<button class="llm-model-card-btn btn-selected" disabled>Indisponivel</button>`;
                } else if (mInfo.status === "ready" || mInfo.status === "downloaded") {
                    if (mInfo.selected) {
                        btnHtml = `<button class="llm-model-card-btn btn-selected" disabled>✓ Ativo</button>`;
                        if (infoLlm) infoLlm.textContent = mInfo.title;
                    } else {
                        btnHtml = `<button class="llm-model-card-btn btn-select" onclick="selectModel('${mId}')">Selecionar</button>`;
                    }
                } else if (mInfo.status === "downloading") {
                    btnHtml = `<span style="font-size:0.78rem;color:#f59e0b;">Baixando...</span>`;
                } else {
                    btnHtml = `<button class="llm-model-card-btn btn-download" onclick="downloadLLM('${mId}')">⭳ Baixar</button>`;
                }

                card.innerHTML = `
                    <div class="llm-model-card-info">
                        <div class="llm-model-card-name">${mInfo.title}</div>
                        <div class="llm-model-card-size">${escHtml(mInfo.supported === false ? (mInfo.support_reason || mInfo.size) : mInfo.size)}</div>
                    </div>
                    ${btnHtml}
                `;
                container.appendChild(card);
            }

            if(anyDownloading) setTimeout(fetchLlmStatus, 2000);
        }
    } catch(e) {}
}

window.selectModel = async function(modelId) {
    appConfig.llm_model_id = modelId;
    await performAutoSave(false);
    fetchLlmStatus();
}

window.downloadLLM = async function(modelId) {
    appConfig.llm_model_id = modelId;
    await performAutoSave(false);
    showToast("Download iniciado no console do motor...", "info");
    try {
        await fetch(`${API}/api/llm/download`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model_id: modelId })
        });
        fetchLlmStatus();
    } catch(e) {
        showToast("Erro ao requisitar download", "error");
    }
}

function applyTheme(t) {
    if(t === "light") {
        document.body.classList.add("light-theme");
    } else {
        document.body.classList.remove("light-theme");
    }
}

// ══════════════════════════════════════════════════════════
//  AUDIO PLAYER
// ══════════════════════════════════════════════════════════
function playSong(index) {
    if (index < 0 || index >= songs.length || !els.audio) return;
    currentSongIndex = index;
    const song = songs[index];

    els.audio.src = `${API}/api/songs/${song.filename}`;
    els.audio.play();
    els.playerTitle.textContent = song.title || "Sem Titulo";
    els.playerCaption.textContent = song.caption || "---";
    updatePlayButton(true);
    renderSongs(els.searchSongs.value.toLowerCase());
    if (currentPage === "feed") renderFeed();
}

on(els.btnPlay, "click", () => {
    if (!els.audio.src || els.audio.src === window.location.href) return;
    if (els.audio.paused) {
        els.audio.play();
        updatePlayButton(true);
    } else {
        els.audio.pause();
        updatePlayButton(false);
    }
});

on(els.btnPrev, "click", () => {
    if (currentSongIndex > 0) playSong(currentSongIndex - 1);
});

on(els.btnNext, "click", () => {
    if (currentSongIndex < songs.length - 1) playSong(currentSongIndex + 1);
});

function updatePlayButton(playing) {
    els.playIcon?.classList.toggle("hidden", playing);
    els.pauseIcon?.classList.toggle("hidden", !playing);
}

on(els.audio, "timeupdate", () => {
    if (!els.audio.duration) return;
    const pct = (els.audio.currentTime / els.audio.duration) * 100;
    els.progressFill.style.width = pct + "%";
    els.progressThumb.style.left = pct + "%";
    els.timeCurrent.textContent = formatTime(els.audio.currentTime);
});

on(els.audio, "loadedmetadata", () => {
    els.timeTotal.textContent = formatTime(els.audio.duration);
});

on(els.audio, "ended", () => {
    updatePlayButton(false);
    if (currentSongIndex < songs.length - 1) {
        playSong(currentSongIndex + 1);
    }
});

on(els.audio, "pause", () => updatePlayButton(false));
on(els.audio, "play", () => updatePlayButton(true));

// Seek
on(els.progressTrack, "click", (e) => {
    if (!els.audio.duration) return;
    const rect = els.progressTrack.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    els.audio.currentTime = pct * els.audio.duration;
});

// Volume
on(els.volumeSlider, "input", () => {
    els.audio.volume = parseFloat(els.volumeSlider.value);
});
if (els.audio) els.audio.volume = 0.8;

// ══════════════════════════════════════════════════════════
//  SERVER STATUS
// ══════════════════════════════════════════════════════════
function updateServerStatus(status) {
    if (!els.serverStatus) return;
    const dot = els.serverStatus.querySelector(".status-dot");
    const text = els.serverStatus.querySelector(".status-text");
    dot.className = "status-dot " + status;
    const labels = { online: "Online", offline: "Offline", connecting: "Carregando..." };
    text.textContent = labels[status] || status;
}

async function checkServerHealth() {
    try {
        const res = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(3000) });
        const data = await res.json();
        const healthMode = data.status === "standby" ? "standby" : "online";
        serverReady = data.status === "online" || data.status === "standby";
        updateServerStatus(serverReady ? "online" : "connecting");
        if (serverReady) {
            if (els.btnGenerate) els.btnGenerate.disabled = false;
            if (els.infoStatus) els.infoStatus.textContent = healthMode === "standby" ? "Pronto sob demanda" : "Online";
            if (data.gpu && els.infoGpu) els.infoGpu.textContent = data.gpu;
        } else {
            if (els.btnGenerate) els.btnGenerate.disabled = true;
            if (els.infoStatus) els.infoStatus.textContent = "Carregando";
        }
    } catch {
        updateServerStatus("offline");
        serverReady = false;
        if (els.btnGenerate) els.btnGenerate.disabled = true;
        if (els.infoStatus) els.infoStatus.textContent = "Offline";
    }
}

// ══════════════════════════════════════════════════════════
//  UTILITIES
// ══════════════════════════════════════════════════════════
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function formatTime(sec) {
    if (!sec || isNaN(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m + ":" + String(s).padStart(2, "0");
}

function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

function escAttr(str) {
    return (str || "").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = "toast " + type;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

// ══════════════════════════════════════════════════════════
//  VOICE CLONE
// ══════════════════════════════════════════════════════════
const voiceUpload = els.voiceUpload;
const voiceSelect = els.voiceSelect;

on(els.btnUploadAudio, "click", () => {
    voiceUpload?.click();
});

if (voiceUpload) {
    voiceUpload.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        showToast("Enviando voz...", "info");
        try {
            const res = await fetch(`${API}/api/upload-voice`, {
                method: "POST",
                body: formData,
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Voz "${data.filename}" salva!`, "success");
                await loadVoices();
                // Seleciona a voz recem enviada
                if (voiceSelect) voiceSelect.value = data.filename;
            } else {
                showToast(data.error || "Erro no upload", "error");
            }
        } catch (err) {
            showToast("Erro ao enviar voz: " + err.message, "error");
        }
        voiceUpload.value = "";
    });
}

async function loadVoices() {
    if (!voiceSelect) return;
    try {
        const res = await fetch(`${API}/api/voices`);
        const voices = await res.json();
        // Mantém a opção padrão
        voiceSelect.innerHTML = '<option value="">Nenhuma (voz padrao da IA)</option>';
        voices.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.filename;
            opt.textContent = `${v.filename} (${v.size_kb} KB)`;
            voiceSelect.appendChild(opt);
        });
    } catch (e) {
        console.log("Erro carregar vozes na config", e);
    }
}

// Initialization logic replaced completely with dynamic save manager in settings.
// Legacy Reload Button fallback if someone keeps the code snippet somewhere
// though it is removed from UI in new design.


// ══════════════════════════════════════════════════════════
//  EXTEND SONG
// ══════════════════════════════════════════════════════════
async function extendSong(filename, caption) {
    if (isGenerating) {
        showToast("Aguarde a geracao atual terminar.", "error");
        return;
    }

    const duration = prompt("Quantos segundos deseja estender?", "30");
    if (!duration) return;

    isGenerating = true;
    showToast("Estendendo musica... Isso pode demorar.", "info");

    try {
        const res = await fetch(`${API}/api/extend`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                filename: filename,
                duration: parseInt(duration),
                caption: caption || "",
            }),
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Musica estendida! Duracao total: ${data.duration}s`, "success");
            await loadSongs();
            if (currentPage === "feed") renderFeed();
        } else {
            showToast(data.error || "Falha na extensao", "error");
        }
    } catch (e) {
        showToast("Erro: " + e.message, "error");
    } finally {
        isGenerating = false;
    }
}

// ══════════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
    initializeAppShell();
    initializeBootState();
    navigateTo(resolvePageFromLocation(), { updateHistory: false, replaceHistory: true });
    checkServerHealth();

    // Periodic health check
    setInterval(checkServerHealth, 15000);

    // Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
        if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
        if (e.code === "Space" && els.btnPlay) { e.preventDefault(); els.btnPlay.click(); }
    });

    // ══════════════════════════════════════════════════════════
    //  CHAT IA MODULE
    // ══════════════════════════════════════════════════════════
    if (!document.getElementById("chat-file-input")) {
        const chatInput = document.getElementById("chat-input");
        const chatSendBtn = document.getElementById("chat-send-btn");
        const chatScrollArea = document.getElementById("chat-scroll-area");
        const chatEmptyState = document.getElementById("chat-empty-state");
        const chatSuggestions = document.querySelectorAll(".suggestion-btn");

        let chatHistory = []; // Internal memory to send to API

    function setMessageContent(contentEl, content) {
        contentEl.innerHTML = escHtml(content || "").replace(/\n/g, "<br>");
    }

    function createMessageElement(role, content) {
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message ${role === "user" ? "msg-user" : "msg-ai"}`;
        wrapper.innerHTML = `
            <div class="msg-avatar">${role === "user" ? "EU" : "LY"}</div>
            <div class="msg-bubble">
                <div class="msg-content"></div>
            </div>
        `;
        setMessageContent(wrapper.querySelector(".msg-content"), content);
        return wrapper;
    }

    function createStreamingMessage() {
        const wrapper = createMessageElement("ai", "");
        return {
            wrapper,
            contentEl: wrapper.querySelector(".msg-content"),
        };
    }

    function showTyping() {
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message msg-ai typing-indicator`;
        wrapper.innerHTML = `
            <div class="msg-avatar">LY</div>
            <div class="msg-bubble">
                <div class="msg-content">
                    <span class="dot" style="display:inline-block; animation: msg-dots 1.5s infinite;">.</span>
                    <span class="dot" style="display:inline-block; animation: msg-dots 1.5s infinite 0.2s;">.</span>
                    <span class="dot" style="display:inline-block; animation: msg-dots 1.5s infinite 0.4s;">.</span>
                </div>
            </div>
        `;
        wrapper.id = "chat-typing";
        chatScrollArea.appendChild(wrapper);
        scrollToBottomChat();
    }

    function removeTyping() {
        const ti = document.getElementById("chat-typing");
        if(ti) ti.remove();
    }

    function scrollToBottomChat() {
        setTimeout(() => {
            const conversation = document.getElementById("chat-conversation");
            if (conversation) {
                conversation.scrollTop = conversation.scrollHeight;
            }
        }, 50);
    }

    async function sendChatMessageLegacy(text) {
        if(!text.trim()) return;
        
        if(chatEmptyState) chatEmptyState.style.display = "none";
        
        chatHistory.push({role: "user", content: text});
        chatScrollArea.appendChild(createMessageElement("user", text));
        scrollToBottomChat();
        
        chatInput.value = "";
        showTyping();
        chatSendBtn.disabled = true;
        
        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: chatHistory })
            });
            const data = await response.json();
            removeTyping();
            
            if(response.ok && data.success) {
                chatHistory.push({role: "assistant", content: data.reply});
                chatScrollArea.appendChild(createMessageElement("ai", data.reply));
            } else {
                console.error(data.error);
                chatScrollArea.appendChild(createMessageElement("ai", "Infelizmente, ocorreu um erro de conexão com a IA: " + (data.error || "Nenhum LLM Ativo.")));
            }
        } catch (e) {
            removeTyping();
            chatScrollArea.appendChild(createMessageElement("ai", "Erro ao conectar com API de Chat. Servidor offline?"));
        }
        
        chatSendBtn.disabled = false;
        scrollToBottomChat();
    }

    async function readSseStream(response, onEvent) {
        if (!response.body) {
            throw new Error("Streaming nao disponivel neste navegador.");
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

            let boundary = buffer.indexOf("\n\n");
            while (boundary !== -1) {
                const rawEvent = buffer.slice(0, boundary);
                buffer = buffer.slice(boundary + 2);
                const payload = rawEvent
                    .split(/\r?\n/)
                    .filter((line) => line.startsWith("data:"))
                    .map((line) => line.slice(5).trimStart())
                    .join("\n");

                if (payload) onEvent(JSON.parse(payload));
                boundary = buffer.indexOf("\n\n");
            }

            if (done) break;
        }
    }

    async function sendChatMessage(text) {
        if (!text.trim() || !chatInput || !chatSendBtn || !chatScrollArea) return;

        if (chatEmptyState) chatEmptyState.style.display = "none";

        chatHistory.push({ role: "user", content: text });
        chatScrollArea.appendChild(createMessageElement("user", text));
        scrollToBottomChat();

        chatInput.value = "";
        chatSendBtn.disabled = true;

        const assistantMessage = createStreamingMessage();
        chatScrollArea.appendChild(assistantMessage.wrapper);
        setMessageContent(assistantMessage.contentEl, "...");
        scrollToBottomChat();

        let assistantReply = "";

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: chatHistory, stream: true })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || "Nenhum LLM ativo.");
            }

            let streamError = null;
            await readSseStream(response, (event) => {
                if (event.error) {
                    streamError = event.error;
                    return;
                }
                assistantReply = typeof event.text === "string"
                    ? event.text
                    : assistantReply + (event.delta || "");
                setMessageContent(assistantMessage.contentEl, assistantReply || "...");
                scrollToBottomChat();
            });

            if (streamError) {
                throw new Error(streamError);
            }

            assistantReply = assistantReply.trim();
            if (assistantReply) {
                chatHistory.push({ role: "assistant", content: assistantReply });
                setMessageContent(assistantMessage.contentEl, assistantReply);
            } else {
                setMessageContent(assistantMessage.contentEl, "A IA nao retornou conteudo.");
            }
        } catch (e) {
            setMessageContent(
                assistantMessage.contentEl,
                assistantReply || ("Infelizmente, ocorreu um erro de conexao com a IA: " + e.message)
            );
        }

        chatSendBtn.disabled = false;
        scrollToBottomChat();
    }

        if(chatSendBtn && chatInput) {
            chatSendBtn.addEventListener("click", () => sendChatMessage(chatInput.value));
            chatInput.addEventListener("keydown", (e) => {
                if(e.key === "Enter") sendChatMessage(chatInput.value);
            });
        }

        chatSuggestions.forEach(btn => {
            btn.addEventListener("click", () => {
                const promptText = btn.getAttribute("data-prompt");
                if(promptText) chatInput.value = promptText;
                if(chatSendBtn) chatSendBtn.click();
            });
        });
    }

    fetchLlmStatus = async function() {
        const container = document.getElementById("llm-models-container");
        const infoLlm = document.getElementById("info-llm");
        const chatModelBadge = document.getElementById("chat-model-selector");
        if (!container) return;

        try {
            const res = await fetch(`${API}/api/llm/status`);
            if (!res.ok) return;

            const data = await res.json();
            container.innerHTML = "";
            let anyDownloading = false;

            if (infoLlm) {
                if (data.runtime_error) {
                    infoLlm.textContent = "Ollama offline";
                    infoLlm.title = data.runtime_error;
                } else {
                    infoLlm.textContent = data.engine_label || "Ollama online";
                    infoLlm.title = data.notice || "";
                }
            }

            for (const [mId, mInfo] of Object.entries(data.models)) {
                if (mInfo.status === "downloading") anyDownloading = true;

                const card = document.createElement("div");
                card.className = `llm-model-card${mInfo.selected ? " active" : ""}`;

                let btnHtml = "";
                if (mInfo.status === "ready" || mInfo.status === "downloaded") {
                    if (mInfo.selected) {
                        btnHtml = `<button class="llm-model-card-btn btn-selected" disabled>Ativo</button>`;
                        if (chatModelBadge) {
                            chatModelBadge.innerHTML = `${escHtml(mInfo.title)} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`;
                        }
                    } else {
                        btnHtml = `<button class="llm-model-card-btn btn-select" onclick="selectModel('${mId}')">Selecionar</button>`;
                    }
                } else if (mInfo.status === "downloading") {
                    btnHtml = `<span style="font-size:0.78rem;color:#f59e0b;">${escHtml(mInfo.progress || "Preparando...")}</span>`;
                } else {
                    btnHtml = `<button class="llm-model-card-btn btn-download" onclick="downloadLLM('${mId}')">Instalar</button>`;
                }

                card.innerHTML = `
                    <div class="llm-model-card-info">
                        <div class="llm-model-card-name">${escHtml(mInfo.title)}</div>
                        <div class="llm-model-card-size">${escHtml(mInfo.description || mInfo.size)}${mInfo.progress ? ` - ${escHtml(mInfo.progress)}` : ""}</div>
                    </div>
                    ${btnHtml}
                `;
                container.appendChild(card);
            }

            if (anyDownloading) setTimeout(fetchLlmStatus, 2000);
        } catch (e) {
            if (infoLlm) {
                infoLlm.textContent = "Ollama indisponivel";
                infoLlm.title = e.message || "Falha ao consultar status.";
            }
        }
    };

    window.selectModel = async function(modelId) {
        appConfig.llm_model_id = modelId;
        await performAutoSave(false);
        window.downloadLLM(modelId, false);
        fetchLlmStatus();
    };

    window.downloadLLM = async function(modelId, notify = true) {
        appConfig.llm_model_id = modelId;
        await performAutoSave(false);
        if (notify) showToast("Preparando modelo no Ollama...", "info");
        try {
            const res = await fetch(`${API}/api/llm/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: modelId })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.error || "Falha ao preparar modelo no Ollama.");
            }
            fetchLlmStatus();
        } catch (e) {
            showToast(e.message || "Erro ao requisitar modelo", "error");
        }
    };

});
