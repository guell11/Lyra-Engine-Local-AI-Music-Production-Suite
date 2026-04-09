document.addEventListener("DOMContentLoaded", () => {
    const chatPage = document.getElementById("page-chat");
    if (!chatPage) return;

    const apiBase = typeof API !== "undefined" ? API : "";
    const CREATE_DRAFT_KEY = "lyra_create_draft_v1";
    const CHAT_SESSIONS_KEY = "lyra_chat_sessions_v3";
    const CHAT_ACTIVE_KEY = "lyra_chat_active_v3";
    const CHAT_WEB_SEARCH_KEY = "lyra_chat_web_search_v1";
    const CHAT_WEB_SEARCH_LEVEL_KEY = "lyra_chat_web_search_level_v1";
    const LEGACY_CHAT_SESSIONS_KEYS = ["lyra_chat_sessions_v2", "lyra_chat_sessions_v1"];
    const LEGACY_CHAT_ACTIVE_KEYS = ["lyra_chat_active_v2", "lyra_chat_active_v1"];

    const escapeHtml = typeof escHtml === "function"
        ? escHtml
        : (value) => String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");

    const notify = typeof showToast === "function"
        ? showToast
        : (message) => console.log(message);

    const readFileAsText = (file) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Falha ao ler arquivo."));
        reader.readAsText(file);
    });

    const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Falha ao ler imagem."));
        reader.readAsDataURL(file);
    });

    const chatMain = document.getElementById("chat-main");
    const chatConversation = document.getElementById("chat-conversation");
    const chatScrollArea = document.getElementById("chat-scroll-area");
    const chatHistoryList = document.getElementById("chat-history-list");
    const chatHistoryEmpty = document.getElementById("chat-history-empty");
    const chatAttachmentsBar = document.getElementById("chat-attachments-bar");
    const chatModelBadge = document.getElementById("chat-model-selector");
    const chatWebToggle = document.getElementById("chat-web-toggle");
    const chatWebDepth = document.getElementById("chat-web-depth");
    const chatResearchDock = document.getElementById("chat-research-dock");
    const chatResearchDockContent = document.getElementById("chat-research-dock-content");
    const infoLlm = document.getElementById("info-llm");
    const llmModelsContainer = document.getElementById("llm-models-container");

    const chatInput = document.getElementById("chat-input");
    const chatSendBtn = document.getElementById("chat-send-btn");
    const chatAttachBtn = document.getElementById("chat-attach-btn");
    const chatFileInput = document.getElementById("chat-file-input");
    const chatNewBtn = document.getElementById("chat-new-btn");
    const chatSearchHint = document.getElementById("chat-search-hint");
    const chatContextHint = document.getElementById("chat-context-hint");
    const suggestionButtons = Array.from(document.querySelectorAll(".suggestion-btn"));

    let chatSessions = [];
    let activeChatId = null;
    let llmStatusTimer = null;
    let pendingAttachments = [];
    let webSearchEnabled = localStorage.getItem(CHAT_WEB_SEARCH_KEY) === "1";
    let webSearchLevel = localStorage.getItem(CHAT_WEB_SEARCH_LEVEL_KEY) || "basic";

    const normalizeLanguage = (rawValue) => {
        const value = String(rawValue || "").trim().toLowerCase();
        if (!value) return "";
        if (["pt", "pt-br", "portugues", "portuguese"].includes(value)) return "pt";
        if (["en", "english", "ingles"].includes(value)) return "en";
        if (["es", "spanish", "espanhol"].includes(value)) return "es";
        if (["fr", "french", "frances"].includes(value)) return "fr";
        if (["ja", "japanese", "japones"].includes(value)) return "ja";
        if (["ko", "korean", "coreano"].includes(value)) return "ko";
        if (["zh", "chinese", "mandarin"].includes(value)) return "zh";
        return value;
    };

    const inferLanguageFromText = (text) => {
        const sample = String(text || "").trim().toLowerCase();
        if (!sample) return "";
        if (/[ãõçáàâéêíóôú]/.test(sample) || /\b(que|não|nao|pra|voce|você|com|uma|verao|verão)\b/.test(sample)) {
            return "pt";
        }
        if (/\b(the|and|with|summer|love|night|you)\b/.test(sample)) {
            return "en";
        }
        if (/\b(el|la|una|verano|corazon|corazón)\b/.test(sample)) {
            return "es";
        }
        return "";
    };

    const resolveExportLanguage = (payload) => {
        const explicit = normalizeLanguage(payload?.language || "");
        if (explicit) return explicit;

        const inferred = inferLanguageFromText([
            payload?.lyrics || "",
            payload?.caption || "",
            payload?.title || "",
        ].join(" "));
        if (inferred) return inferred;

        try {
            if (typeof appConfig !== "undefined" && appConfig?.defaultLang) {
                const fromConfig = normalizeLanguage(appConfig.defaultLang);
                if (fromConfig) return fromConfig;
            }
        } catch (error) {
            console.debug("Nao foi possivel ler appConfig para inferir idioma", error);
        }

        return "pt";
    };

    const normalizeLabel = (label) => String(label || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");

    const labelToField = (label) => {
        const normalized = normalizeLabel(label);
        if (["lyrics", "letra", "letras"].includes(normalized)) return "lyrics";
        if (["style", "estilo", "ritmo", "ritimo", "rhythm", "descricao", "descricao_ritmo", "prompt", "caption", "arranjo", "arrangement"].includes(normalized)) return "caption";
        if (["duration", "duracao", "seconds", "segundos", "tempo"].includes(normalized)) return "duration";
        if (["title", "titulo"].includes(normalized)) return "title";
        if (["language", "idioma", "lang"].includes(normalized)) return "language";
        if (["bpm"].includes(normalized)) return "bpm";
        return null;
    };

    const normalizeResearchSource = (source) => {
        if (!source || typeof source !== "object") return null;
        const title = String(source.title || source.domain || source.url || "").trim();
        const url = String(source.url || "").trim();
        if (!title && !url) return null;
        return {
            id: String(source.id || source.url || source.title || "").trim() || `research_${Date.now()}`,
            title,
            url,
            domain: String(source.domain || "").trim(),
            query: String(source.query || "").trim(),
            excerpt_preview: String(source.excerpt_preview || "").trim(),
            summary: String(source.summary || "").trim(),
            status: String(source.status || "discovered").trim(),
        };
    };

    const upsertResearchSource = (collection, source) => {
        const normalized = normalizeResearchSource(source);
        if (!normalized) return Array.isArray(collection) ? collection : [];
        const current = Array.isArray(collection) ? [...collection] : [];
        const index = current.findIndex((item) =>
            item.id === normalized.id
            || (normalized.url && item.url === normalized.url)
            || (normalized.title && item.title === normalized.title)
        );
        if (index >= 0) {
            current[index] = { ...current[index], ...normalized };
            return current;
        }
        current.push(normalized);
        return current;
    };

    const humanizeResearchStatus = (status) => {
        const normalized = String(status || "").trim().toLowerCase();
        if (normalized === "discovered") return "novo";
        if (normalized === "fetching") return "lendo";
        if (normalized === "summarizing") return "resumindo";
        if (normalized === "ready") return "pronto";
        if (normalized === "error") return "erro";
        if (normalized === "planning") return "planejando";
        if (normalized === "searching") return "buscando";
        if (normalized === "answering") return "respondendo";
        return normalized || "novo";
    };

    const getResearchFaviconUrl = (source) => {
        const target = String(source?.url || source?.domain || "").trim();
        if (!target) return "";
        const domainUrl = target.startsWith("http://") || target.startsWith("https://")
            ? target
            : `https://${target}`;
        return `https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(domainUrl)}`;
    };

    const getResearchSourceLabel = (source) => (
        source?.title
        || source?.domain
        || source?.url
        || "Fonte"
    );

    const getResearchInitials = (source) => {
        const domain = String(source?.domain || "").replace(/^www\./i, "").trim();
        if (domain) return domain.slice(0, 2).toUpperCase();
        return getResearchSourceLabel(source)
            .split(/\s+/)
            .map((part) => part[0] || "")
            .join("")
            .slice(0, 2)
            .toUpperCase() || "WB";
    };

    const normalizeStoredMessage = (message) => {
        if (!message || typeof message !== "object") return null;
        const role = message.role === "assistant" ? "assistant" : "user";
        const rawContent = [
            message.content,
            message.display_content,
            message.text,
            message.message,
            message.reply,
            message.body,
        ].find((value) => typeof value === "string" && value.trim());
        const rawDisplay = [
            message.display_content,
            message.display,
            message.preview,
            message.summary,
            rawContent,
        ].find((value) => typeof value === "string" && value.trim());
        const content = typeof rawContent === "string" ? rawContent.trim() : "";
        const displayContent = typeof rawDisplay === "string" ? rawDisplay.trim() : content;
        if (!content && !displayContent) return null;
        return {
            role,
            content: content || displayContent,
            display_content: displayContent || content,
            images: Array.isArray(message.images)
                ? message.images.filter((item) => typeof item === "string" && item.trim()).slice(0, 3)
                : [],
            research: Array.isArray(message.research)
                ? message.research.map(normalizeResearchSource).filter(Boolean)
                : [],
            research_queries: Array.isArray(message.research_queries)
                ? message.research_queries.map((item) => String(item || "").trim()).filter(Boolean)
                : [],
            research_status: typeof message.research_status === "string" ? message.research_status.trim() : "",
            research_collapsed: Boolean(message.research_collapsed),
        };
    };

    const normalizeStoredSession = (session, index = 0) => {
        if (!session || typeof session !== "object") return null;
        const normalizedMessages = Array.isArray(session.messages)
            ? session.messages.map(normalizeStoredMessage).filter(Boolean)
            : [];
        const fallbackTitle = buildChatTitle(
            session.seed
            || session.prompt
            || session.topic
            || normalizedMessages[0]?.display_content
            || normalizedMessages[0]?.content
            || "Novo chat"
        );
        return {
            id: typeof session.id === "string" ? session.id : `chat_${Date.now()}_${index}`,
            title: typeof session.title === "string" && session.title.trim() ? session.title.trim() : fallbackTitle,
            createdAt: typeof session.createdAt === "string" ? session.createdAt : new Date(Date.now() - index).toISOString(),
            updatedAt: typeof session.updatedAt === "string" ? session.updatedAt : new Date(Date.now() - index).toISOString(),
            messages: normalizedMessages,
        };
    };

    const serializeMessage = (message) => ({
        role: message.role === "assistant" ? "assistant" : "user",
        content: String(message.content || message.display_content || "").trim(),
        display_content: String(message.display_content || message.content || "").trim(),
        images: Array.isArray(message.images)
            ? message.images.filter((item) => typeof item === "string" && item.trim()).slice(0, 3)
            : [],
        research: Array.isArray(message.research)
            ? message.research.map(normalizeResearchSource).filter(Boolean)
            : [],
        research_queries: Array.isArray(message.research_queries)
            ? message.research_queries.map((item) => String(item || "").trim()).filter(Boolean)
            : [],
        research_status: typeof message.research_status === "string" ? message.research_status.trim() : "",
        research_collapsed: Boolean(message.research_collapsed),
    });

    const sortSessions = () => {
        chatSessions = [...chatSessions].sort(
            (left, right) => new Date(right.updatedAt) - new Date(left.updatedAt)
        );
    };

    const loadChatState = () => {
        try {
            let rawSessions = localStorage.getItem(CHAT_SESSIONS_KEY);
            if (!rawSessions) {
                for (const legacyKey of LEGACY_CHAT_SESSIONS_KEYS) {
                    rawSessions = localStorage.getItem(legacyKey);
                    if (rawSessions) break;
                }
            }

            let rawActive = localStorage.getItem(CHAT_ACTIVE_KEY);
            if (!rawActive) {
                for (const legacyKey of LEGACY_CHAT_ACTIVE_KEYS) {
                    rawActive = localStorage.getItem(legacyKey);
                    if (rawActive) break;
                }
            }

            const parsedSessions = JSON.parse(rawSessions || "[]");
            chatSessions = Array.isArray(parsedSessions)
                ? parsedSessions.map((session, index) => normalizeStoredSession(session, index)).filter(Boolean)
                : [];
            activeChatId = rawActive || null;
        } catch (error) {
            console.warn("Falha ao carregar historico do chat", error);
            chatSessions = [];
            activeChatId = null;
        }

        sortSessions();
        if (activeChatId && !chatSessions.some((session) => session.id === activeChatId)) {
            activeChatId = null;
        }
        if (!activeChatId && chatSessions.length) {
            activeChatId = chatSessions[0].id;
        }
    };

    const persistChatState = () => {
        try {
            sortSessions();
            const safeSessions = chatSessions.map((session) => ({
                id: session.id,
                title: session.title,
                createdAt: session.createdAt,
                updatedAt: session.updatedAt,
                messages: (session.messages || []).map(serializeMessage),
            }));
            localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(safeSessions));
            if (activeChatId) {
                localStorage.setItem(CHAT_ACTIVE_KEY, activeChatId);
            } else {
                localStorage.removeItem(CHAT_ACTIVE_KEY);
            }

            LEGACY_CHAT_SESSIONS_KEYS.forEach((key) => localStorage.removeItem(key));
            LEGACY_CHAT_ACTIVE_KEYS.forEach((key) => localStorage.removeItem(key));
        } catch (error) {
            console.warn("Falha ao salvar historico do chat", error);
        }
    };

    const buildChatTitle = (text) => {
        const compact = String(text || "").replace(/\s+/g, " ").trim();
        if (!compact) return "Novo chat";
        return compact.length > 42 ? `${compact.slice(0, 39)}...` : compact;
    };

    const getActiveSession = () => chatSessions.find((session) => session.id === activeChatId) || null;

    const ensureActiveSession = (seedText = "") => {
        let session = getActiveSession();
        if (session) return session;

        session = {
            id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            title: buildChatTitle(seedText),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            messages: [],
        };
        chatSessions.unshift(session);
        activeChatId = session.id;
        persistChatState();
        return session;
    };

    const setChatState = (hasMessages) => {
        if (!chatMain) return;
        chatMain.classList.toggle("chat-state-active", hasMessages);
        chatMain.classList.toggle("chat-state-empty", !hasMessages);
    };

    const scrollToBottom = () => {
        setTimeout(() => {
            if (chatConversation) {
                chatConversation.scrollTop = chatConversation.scrollHeight;
            }
        }, 40);
    };

    const parseFallbackStructuredBlocks = (text) => {
        const lines = String(text || "").split(/\r?\n/);
        const parts = [];
        const blocks = [];
        const labelOnlyRegex = /^([\p{L}][\p{L}0-9 _/\-]{1,40})\s*:?\s*$/u;
        const inlineRegex = /^([\p{L}][\p{L}0-9 _/\-]{1,40})\s*:\s*(.+)$/u;
        let textBuffer = [];
        let activeBlock = null;

        const flushText = () => {
            if (!textBuffer.length) return;
            const value = textBuffer.join("\n").trim();
            textBuffer = [];
            if (value) {
                parts.push({ type: "text", value });
            }
        };

        const flushBlock = () => {
            if (!activeBlock) return;
            const value = activeBlock.lines.join("\n").trim();
            if (value) {
                const block = {
                    type: "block",
                    rawLabel: activeBlock.rawLabel,
                    label: activeBlock.label,
                    field: activeBlock.field,
                    value,
                };
                parts.push(block);
                blocks.push(block);
            }
            activeBlock = null;
        };

        lines.forEach((line) => {
            const trimmed = line.trim();
            const inlineMatch = trimmed.match(inlineRegex);
            if (inlineMatch) {
                const rawLabel = inlineMatch[1].trim();
                const field = labelToField(rawLabel);
                if (field) {
                    flushText();
                    flushBlock();
                    const block = {
                        type: "block",
                        rawLabel,
                        label: normalizeLabel(rawLabel),
                        field,
                        value: inlineMatch[2].trim(),
                    };
                    parts.push(block);
                    blocks.push(block);
                    return;
                }
            }

            const labelOnlyMatch = trimmed.match(labelOnlyRegex);
            if (labelOnlyMatch) {
                const rawLabel = labelOnlyMatch[1].trim();
                const field = labelToField(rawLabel);
                if (field) {
                    flushText();
                    flushBlock();
                    activeBlock = {
                        rawLabel,
                        label: normalizeLabel(rawLabel),
                        field,
                        lines: [],
                    };
                    return;
                }
            }

            if (activeBlock) {
                activeBlock.lines.push(line);
            } else {
                textBuffer.push(line);
            }
        });

        flushText();
        flushBlock();
        return { parts, blocks };
    };

    const parseStructuredBlocks = (content) => {
        const text = String(content || "").replace(/\u00B4{3,}/g, "```");
        const regex = /```([^\n`]*)\n([\s\S]*?)```/g;
        const parts = [];
        const blocks = [];
        let lastIndex = 0;
        let match;

        while ((match = regex.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
            }
            const rawLabel = (match[1] || "bloco").trim() || "bloco";
            const code = String(match[2] || "").replace(/\s+$/, "");
            const label = normalizeLabel(rawLabel);
            const field = labelToField(label);
            const block = { type: "block", rawLabel, label, field, value: code };
            parts.push(block);
            blocks.push(block);
            lastIndex = regex.lastIndex;
        }

        if (lastIndex < text.length) {
            parts.push({ type: "text", value: text.slice(lastIndex) });
        }

        if (!blocks.length) {
            return parseFallbackStructuredBlocks(text);
        }
        return { parts, blocks };
    };

    const extractExportPayload = (content) => {
        const { blocks } = parseStructuredBlocks(content);
        const payload = {};

        blocks.forEach((block) => {
            if (!block.field) return;
            const value = String(block.value || "").trim();
            if (!value) return;

            if (block.field === "duration") {
                const match = value.match(/\d+/);
                if (match) {
                    const duration = Math.max(5, Math.min(600, parseInt(match[0], 10)));
                    payload.duration = duration;
                }
                return;
            }

            if (block.field === "language") {
                payload.language = normalizeLanguage(value);
                return;
            }

            if (block.field === "bpm") {
                const match = value.match(/\d+/);
                if (match) payload.bpm = parseInt(match[0], 10);
                return;
            }

            payload[block.field] = value;
        });

        payload.hasUsefulData = Boolean(
            payload.lyrics || payload.caption || payload.duration || payload.title || payload.language || payload.bpm
        );
        return payload;
    };

    const exportToCreate = (payload) => {
        if (!payload || !payload.hasUsefulData) {
            notify("Nao encontrei blocos exportaveis nessa resposta.", "error");
            return;
        }

        const draft = {
            title: payload.title || "",
            caption: payload.caption || "",
            lyrics: payload.lyrics || "",
            duration: payload.duration || "",
            language: resolveExportLanguage(payload),
            bpm: payload.bpm || "",
            ai_prompt: [payload.title, payload.caption].filter(Boolean).join(" - "),
            savedAt: new Date().toISOString(),
        };
        localStorage.setItem(CREATE_DRAFT_KEY, JSON.stringify(draft));
        window.dispatchEvent(new CustomEvent("lyra:create-draft", { detail: draft }));
        notify("Rascunho enviado para a aba Criar.", "success");
        if (typeof window.navigateLyraPage === "function") {
            window.navigateLyraPage("criar");
            return;
        }
        window.location.href = "/";
    };

    const updateWebToggleUi = () => {
        if (!chatWebToggle) return;
        chatWebToggle.setAttribute("aria-pressed", webSearchEnabled ? "true" : "false");
        chatWebToggle.title = webSearchEnabled
            ? "Pesquisa web ativa: a IA pode buscar e resumir sites antes de responder."
            : "Pesquisa web desligada: o chat responde apenas com contexto local.";
    };

    const updateWebDepthUi = () => {
        const allowed = new Set(["basic", "medium", "large"]);
        if (!allowed.has(webSearchLevel)) {
            webSearchLevel = "basic";
        }
        if (chatWebDepth) {
            chatWebDepth.value = webSearchLevel;
            chatWebDepth.title = "Controle quantos sites a IA vai pesquisar e resumir antes da resposta.";
        }
    };

    const messageHasResearch = (message) => {
        if (!message || typeof message !== "object") return false;
        return Boolean(
            (Array.isArray(message.research) && message.research.length)
            || (Array.isArray(message.research_queries) && message.research_queries.length)
            || String(message.research_status || "").trim()
        );
    };

    const getLatestResearchMessage = (session) => {
        const messages = Array.isArray(session?.messages) ? session.messages : [];
        for (let index = messages.length - 1; index >= 0; index -= 1) {
            const message = messages[index];
            if (message?.role === "assistant" && messageHasResearch(message)) {
                return message;
            }
        }
        return null;
    };

    const renderResearchDock = (message = null) => {
        if (!chatResearchDock || !chatResearchDockContent || !chatMain) return;

        if (!messageHasResearch(message)) {
            chatResearchDock.classList.add("hidden");
            chatResearchDock.classList.remove("is-collapsed");
            chatMain.classList.remove("has-research-dock");
            chatResearchDockContent.innerHTML = "";
            return;
        }

        const panel = renderResearchPanelLive(message);
        if (!panel) {
            chatResearchDock.classList.add("hidden");
            chatResearchDock.classList.remove("is-collapsed");
            chatMain.classList.remove("has-research-dock");
            chatResearchDockContent.innerHTML = "";
            return;
        }

        chatResearchDockContent.innerHTML = "";
        chatResearchDockContent.appendChild(panel);
        chatResearchDock.classList.remove("hidden");
        chatResearchDock.classList.toggle("is-collapsed", Boolean(message.research_collapsed));
        chatMain.classList.add("has-research-dock");
    };

    const renderResearchPanel = ({ research = [], researchQueries = [], researchStatus = "" } = {}) => {
        const safeResearch = Array.isArray(research) ? research.map(normalizeResearchSource).filter(Boolean) : [];
        const safeQueries = Array.isArray(researchQueries)
            ? researchQueries.map((item) => String(item || "").trim()).filter(Boolean)
            : [];
        const status = String(researchStatus || "").trim();

        if (!safeResearch.length && !safeQueries.length && !status) {
            return null;
        }

        const panel = document.createElement("div");
        panel.className = "chat-research-panel";

        const header = document.createElement("div");
        header.className = "chat-research-header";
        const title = document.createElement("div");
        title.className = "chat-research-title";
        title.textContent = "Think · Pesquisa web";
        header.appendChild(title);

        if (status) {
            const statusEl = document.createElement("div");
            statusEl.className = "chat-research-status";
            statusEl.textContent = status;
            header.appendChild(statusEl);
        }
        panel.appendChild(header);

        if (safeQueries.length) {
            const queryWrap = document.createElement("div");
            queryWrap.className = "chat-research-queries";
            safeQueries.forEach((query) => {
                const chip = document.createElement("div");
                chip.className = "chat-research-query";
                chip.textContent = query;
                queryWrap.appendChild(chip);
            });
            panel.appendChild(queryWrap);
        }

        if (safeResearch.length) {
            const cards = document.createElement("div");
            cards.className = "chat-research-sources";

            safeResearch.forEach((source) => {
                const card = document.createElement("div");
                const safeStatusClass = String(source.status || "discovered")
                    .toLowerCase()
                    .replace(/[^a-z0-9_-]+/g, "-");
                card.className = `chat-research-card is-${safeStatusClass}`;

                const top = document.createElement("div");
                top.className = "chat-research-card-top";

                const titleWrap = document.createElement("div");
                const titleEl = document.createElement("div");
                titleEl.className = "chat-research-card-title";
                titleEl.textContent = source.title || source.domain || "Fonte";
                titleWrap.appendChild(titleEl);

                const domainEl = document.createElement("div");
                domainEl.className = "chat-research-card-domain";
                domainEl.textContent = source.domain || "web";
                titleWrap.appendChild(domainEl);
                top.appendChild(titleWrap);

                const statusEl = document.createElement("div");
                statusEl.className = "chat-research-card-status";
                statusEl.textContent = humanizeResearchStatus(source.status);
                top.appendChild(statusEl);
                card.appendChild(top);

                if (source.summary) {
                    const summaryEl = document.createElement("div");
                    summaryEl.className = "chat-research-card-summary";
                    summaryEl.textContent = source.summary;
                    card.appendChild(summaryEl);
                }

                if (source.url) {
                    const link = document.createElement("a");
                    link.className = "chat-research-card-link";
                    link.href = source.url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = "Abrir fonte";
                    card.appendChild(link);
                }

                cards.appendChild(card);
            });

            panel.appendChild(cards);
        }

        return panel;
    };

    const renderResearchPanelLive = (message = {}) => {
        const safeResearch = Array.isArray(message.research)
            ? message.research.map(normalizeResearchSource).filter(Boolean)
            : [];
        const safeQueries = Array.isArray(message.research_queries)
            ? message.research_queries.map((item) => String(item || "").trim()).filter(Boolean)
            : [];
        const status = String(message.research_status || "").trim();

        if (!safeResearch.length && !safeQueries.length && !status) {
            return null;
        }

        const panel = document.createElement("div");
        panel.className = `chat-research-panel${message.research_collapsed ? " is-collapsed" : ""}`;

        const header = document.createElement("div");
        header.className = "chat-research-header";

        const heading = document.createElement("div");
        heading.className = "chat-research-heading";

        const title = document.createElement("div");
        title.className = "chat-research-title";
        title.textContent = "Think - Pesquisa web";
        heading.appendChild(title);

        if (status) {
            const statusEl = document.createElement("div");
            statusEl.className = "chat-research-status";
            statusEl.textContent = status;
            heading.appendChild(statusEl);
        }
        header.appendChild(heading);

        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "chat-research-toggle";
        toggleBtn.textContent = message.research_collapsed ? "Mostrar" : "Ocultar";
        toggleBtn.setAttribute("aria-expanded", message.research_collapsed ? "false" : "true");
        toggleBtn.addEventListener("click", () => {
            message.research_collapsed = !Boolean(message.research_collapsed);
            panel.classList.toggle("is-collapsed", Boolean(message.research_collapsed));
            toggleBtn.textContent = message.research_collapsed ? "Mostrar" : "Ocultar";
            toggleBtn.setAttribute("aria-expanded", message.research_collapsed ? "false" : "true");
            persistChatState();
        });
        header.appendChild(toggleBtn);
        panel.appendChild(header);

        const body = document.createElement("div");
        body.className = "chat-research-body";

        if (safeQueries.length) {
            const queryWrap = document.createElement("div");
            queryWrap.className = "chat-research-queries";
            safeQueries.forEach((query) => {
                const chip = document.createElement("div");
                chip.className = "chat-research-query";
                chip.textContent = query;
                queryWrap.appendChild(chip);
            });
            body.appendChild(queryWrap);
        }

        if (safeResearch.length) {
            const cards = document.createElement("div");
            cards.className = "chat-research-sources";

            safeResearch.forEach((source) => {
                const card = document.createElement("div");
                const safeStatusClass = String(source.status || "discovered")
                    .toLowerCase()
                    .replace(/[^a-z0-9_-]+/g, "-");
                card.className = `chat-research-card is-${safeStatusClass}`;

                const top = document.createElement("div");
                top.className = "chat-research-card-top";

                const brand = document.createElement("div");
                brand.className = "chat-research-card-brand";

                const faviconWrap = document.createElement("div");
                faviconWrap.className = "chat-research-favicon-wrap";

                const favicon = document.createElement("img");
                favicon.className = "chat-research-favicon";
                favicon.alt = "";
                favicon.loading = "lazy";
                favicon.referrerPolicy = "no-referrer";
                favicon.src = getResearchFaviconUrl(source);
                if (favicon.src) {
                    favicon.addEventListener("error", () => faviconWrap.classList.add("is-fallback"));
                } else {
                    faviconWrap.classList.add("is-fallback");
                }

                const faviconFallback = document.createElement("div");
                faviconFallback.className = "chat-research-favicon-fallback";
                faviconFallback.textContent = getResearchInitials(source);

                faviconWrap.appendChild(favicon);
                faviconWrap.appendChild(faviconFallback);
                brand.appendChild(faviconWrap);

                const titleWrap = document.createElement("div");
                titleWrap.className = "chat-research-card-title-wrap";

                const titleEl = document.createElement("div");
                titleEl.className = "chat-research-card-title";
                titleEl.textContent = getResearchSourceLabel(source);
                titleWrap.appendChild(titleEl);

                const domainEl = document.createElement("div");
                domainEl.className = "chat-research-card-domain";
                domainEl.textContent = source.domain || "web";
                titleWrap.appendChild(domainEl);

                brand.appendChild(titleWrap);
                top.appendChild(brand);

                const statusEl = document.createElement("div");
                statusEl.className = "chat-research-card-status";
                statusEl.textContent = humanizeResearchStatus(source.status);
                top.appendChild(statusEl);
                card.appendChild(top);

                if (source.excerpt_preview) {
                    const excerptEl = document.createElement("div");
                    excerptEl.className = "chat-research-card-excerpt";
                    excerptEl.textContent = source.excerpt_preview;
                    card.appendChild(excerptEl);
                }

                if (source.summary) {
                    const summaryEl = document.createElement("div");
                    summaryEl.className = "chat-research-card-summary";
                    summaryEl.textContent = source.summary;
                    card.appendChild(summaryEl);
                }

                if (source.url) {
                    const link = document.createElement("a");
                    link.className = "chat-research-card-link";
                    link.href = source.url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = "Abrir fonte";
                    card.appendChild(link);
                }

                cards.appendChild(card);
            });

            body.appendChild(cards);
        }

        panel.appendChild(body);
        return panel;
    };

    const renderRichContent = (content) => {
        const wrapper = document.createElement("div");
        wrapper.className = "msg-rich-content";

        const parsed = parseStructuredBlocks(content);
        const exportPayload = extractExportPayload(content);

        if (!parsed.blocks.length) {
            const textNode = document.createElement("div");
            textNode.className = "msg-text-fragment";
            textNode.innerHTML = escapeHtml(content || "").replace(/\n/g, "<br>");
            wrapper.appendChild(textNode);
            return { node: wrapper, exportPayload };
        }

        parsed.parts.forEach((part) => {
            if (part.type === "text") {
                const value = String(part.value || "").trim();
                if (!value) return;
                const textNode = document.createElement("div");
                textNode.className = "msg-text-fragment";
                textNode.innerHTML = escapeHtml(value).replace(/\n/g, "<br>");
                wrapper.appendChild(textNode);
                return;
            }

            const blockNode = document.createElement("div");
            blockNode.className = "chat-structured-block";
            blockNode.innerHTML = `
                <div class="chat-structured-label">${escapeHtml(part.rawLabel || "bloco")}</div>
                <pre>${escapeHtml(part.value || "")}</pre>
            `;
            wrapper.appendChild(blockNode);
        });

        return { node: wrapper, exportPayload };
    };

    const renderMessageContent = (wrapper, message) => {
        const isUser = message.role !== "assistant";
        const contentEl = wrapper.querySelector(".msg-content");
        if (!contentEl) return wrapper;

        contentEl.innerHTML = "";
        const plainContent = String(message.display_content || message.content || "");
        const hasVisibleContent = plainContent.trim().length > 0;

        if (!isUser && !hasVisibleContent) {
            const typing = document.createElement("div");
            typing.className = "chat-typing";
            typing.innerHTML = `
                <span class="chat-typing-dot"></span>
                <span class="chat-typing-dot"></span>
                <span class="chat-typing-dot"></span>
            `;
            contentEl.appendChild(typing);
            return wrapper;
        }

        const rendered = renderRichContent(plainContent);
        contentEl.appendChild(rendered.node);

        if (Array.isArray(message.images) && message.images.length) {
            const attachmentsMeta = document.createElement("div");
            attachmentsMeta.className = "chat-message-attachments";
            attachmentsMeta.textContent = `${message.images.length} arquivo(s) de imagem anexado(s)`;
            contentEl.appendChild(attachmentsMeta);
        }

        if (!isUser && rendered.exportPayload?.hasUsefulData) {
            const actions = document.createElement("div");
            actions.className = "chat-message-actions";
            const exportBtn = document.createElement("button");
            exportBtn.type = "button";
            exportBtn.className = "chat-export-btn";
            exportBtn.textContent = "Exportar para Criar";
            exportBtn.addEventListener("click", () => exportToCreate(rendered.exportPayload));
            actions.appendChild(exportBtn);
            contentEl.appendChild(actions);
        }

        return wrapper;
    };

    const createMessageElement = (message) => {
        const role = message.role === "assistant" ? "assistant" : "user";
        const isUser = role === "user";
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message ${isUser ? "msg-user" : "msg-ai"}`;
        wrapper.innerHTML = `
            <div class="msg-avatar">${isUser ? "EU" : "LY"}</div>
            <div class="msg-bubble">
                <div class="msg-content"></div>
            </div>
        `;
        return renderMessageContent(wrapper, message);
    };

    const renderSidebar = () => {
        if (!chatHistoryList || !chatHistoryEmpty) return;

        chatHistoryList.innerHTML = "";
        chatHistoryEmpty.style.display = chatSessions.length ? "none" : "block";

        chatSessions.forEach((session) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `chat-history-item${session.id === activeChatId ? " active" : ""}`;
            button.textContent = session.title || "Novo chat";
            button.title = session.title || "Novo chat";
            button.addEventListener("click", () => {
                activeChatId = session.id;
                persistChatState();
                renderSidebar();
                renderMessages();
            });
            chatHistoryList.appendChild(button);
        });
    };

    const renderMessages = () => {
        if (!chatScrollArea) return;
        chatScrollArea.innerHTML = "";

        let session = getActiveSession();
        if (!session && chatSessions.length) {
            activeChatId = chatSessions[0].id;
            session = getActiveSession();
        }
        const messages = session?.messages || [];
        setChatState(messages.length > 0);

        messages.forEach((message) => {
            chatScrollArea.appendChild(createMessageElement(message));
        });

        renderResearchDock(getLatestResearchMessage(session));
        scrollToBottom();
    };

    const renderPendingAttachments = () => {
        if (!chatAttachmentsBar) return;
        chatAttachmentsBar.innerHTML = "";
        chatAttachmentsBar.style.display = pendingAttachments.length ? "flex" : "none";

        pendingAttachments.forEach((attachment) => {
            const chip = document.createElement("div");
            chip.className = "chat-attachment-chip";
            chip.innerHTML = `
                <span class="chat-attachment-kind">${attachment.type === "image" ? "IMG" : "TXT"}</span>
                <span class="chat-attachment-name">${escapeHtml(attachment.name)}</span>
            `;

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "chat-attachment-remove";
            removeBtn.setAttribute("aria-label", `Remover ${attachment.name}`);
            removeBtn.textContent = "×";
            removeBtn.addEventListener("click", () => {
                pendingAttachments = pendingAttachments.filter((item) => item.id !== attachment.id);
                renderPendingAttachments();
            });

            chip.appendChild(removeBtn);
            chatAttachmentsBar.appendChild(chip);
        });
    };

    const handleSelectedFiles = async (files) => {
        const pickedFiles = Array.from(files || []);
        if (!pickedFiles.length) return;

        for (const file of pickedFiles) {
            const id = `file_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
            const lowerName = file.name.toLowerCase();

            try {
                if (file.type.startsWith("image/")) {
                    const dataUrl = await readFileAsDataUrl(file);
                    pendingAttachments.push({
                        id,
                        type: "image",
                        name: file.name,
                        dataUrl,
                    });
                    continue;
                }

                const isTextFile = file.type.startsWith("text/")
                    || [".txt", ".md", ".json", ".csv"].some((ext) => lowerName.endsWith(ext));

                if (isTextFile) {
                    if (file.size > 250 * 1024) {
                        notify(`Arquivo ${file.name} e grande demais para o chat.`, "error");
                        continue;
                    }
                    const text = await readFileAsText(file);
                    pendingAttachments.push({
                        id,
                        type: "text",
                        name: file.name,
                        text: text.slice(0, 12000),
                    });
                    continue;
                }

                notify(`Formato ainda nao suportado no chat: ${file.name}`, "error");
            } catch (error) {
                notify(`Falha ao ler ${file.name}: ${error.message}`, "error");
            }
        }

        if (chatFileInput) chatFileInput.value = "";
        renderPendingAttachments();
    };

    const buildAttachmentPayload = (promptText) => {
        const cleanPrompt = String(promptText || "").trim();
        const summaryParts = [];
        const modelParts = [];
        const images = [];

        if (cleanPrompt) {
            summaryParts.push(cleanPrompt);
            modelParts.push(cleanPrompt);
        }

        pendingAttachments.forEach((attachment) => {
            if (attachment.type === "text") {
                summaryParts.push(`[arquivo texto anexado: ${attachment.name}]`);
                modelParts.push(
                    `[arquivo texto anexado: ${attachment.name}]\n\`\`\`file\n${attachment.text || ""}\n\`\`\``
                );
            } else if (attachment.type === "image") {
                summaryParts.push(`[imagem anexada: ${attachment.name}]`);
                modelParts.push(`[imagem anexada: ${attachment.name}]`);
                images.push(attachment.dataUrl);
            }
        });

        const displayContent = summaryParts.join("\n");
        const content = modelParts.join("\n\n").trim()
            || "Analise os arquivos anexados e me ajude a montar a musica.";

        return { content, displayContent, images };
    };

    const readSseStream = async (response, onEvent) => {
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
                    } catch (error) {
                        onEvent({ error: "Resposta do stream em formato invalido." });
                    }
                }
                boundary = buffer.indexOf("\n\n");
            }

            if (done) break;
        }
    };

    const sendChatMessage = async (rawText) => {
        if (!chatInput || !chatSendBtn || !chatScrollArea) return;

        const attachmentPayload = buildAttachmentPayload(rawText);
        const messageForModel = attachmentPayload.content.trim();
        if (!messageForModel) return;

        const sessionSeed = String(rawText || "").trim() || pendingAttachments[0]?.name || "Novo chat";
        const session = ensureActiveSession(sessionSeed);
        if (!session.messages.length) {
            session.title = buildChatTitle(sessionSeed);
        }

        const userMessage = {
            role: "user",
            content: messageForModel,
            display_content: attachmentPayload.displayContent || messageForModel,
        };
        if (attachmentPayload.images.length) {
            userMessage.images = attachmentPayload.images;
        }

        session.messages.push(userMessage);
        session.updatedAt = new Date().toISOString();
        persistChatState();
        renderSidebar();
        setChatState(true);

        chatScrollArea.appendChild(createMessageElement(userMessage));
        scrollToBottom();

        chatInput.value = "";
        pendingAttachments = [];
        renderPendingAttachments();
        chatSendBtn.disabled = true;

        const assistantMessage = {
            role: "assistant",
            content: "",
            display_content: "",
            research: [],
            research_queries: [],
            research_status: webSearchEnabled ? "Preparando pesquisa..." : "",
            research_collapsed: false,
        };
        let assistantElement = createMessageElement(assistantMessage);
        chatScrollArea.appendChild(assistantElement);
        scrollToBottom();

        const redrawAssistant = () => {
            renderMessageContent(assistantElement, assistantMessage);
            renderResearchDock(assistantMessage);
            scrollToBottom();
        };

        try {
            const response = await fetch(`${apiBase}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    messages: session.messages,
                    stream: true,
                    web_search_enabled: webSearchEnabled,
                    web_search_level: webSearchLevel,
                }),
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || "Falha ao conversar com o modelo.");
            }

            const contentType = String(response.headers.get("content-type") || "").toLowerCase();
            if (!contentType.includes("text/event-stream")) {
                const data = await response.json().catch(() => ({}));
                if (data?.success && typeof data.reply === "string") {
                    assistantMessage.content = data.reply.trim();
                    assistantMessage.display_content = assistantMessage.content;
                    assistantMessage.research = Array.isArray(data.research)
                        ? data.research.map(normalizeResearchSource).filter(Boolean)
                        : assistantMessage.research;
                    if (assistantMessage.research.length) {
                        assistantMessage.research_status = "Pesquisa concluida.";
                    }
                } else {
                    throw new Error(data?.error || "Resposta invalida da IA.");
                }
            } else {
                let streamError = null;
                await readSseStream(response, (event) => {
                    if (event.error) {
                        streamError = event.error;
                        return;
                    }

                    if (event.type === "research_queries") {
                        assistantMessage.research_queries = Array.isArray(event.queries)
                            ? event.queries.map((item) => String(item || "").trim()).filter(Boolean)
                            : [];
                        redrawAssistant();
                        return;
                    }

                    if (event.type === "research_status") {
                        assistantMessage.research_status = String(event.message || "").trim();
                        redrawAssistant();
                        return;
                    }

                    if (event.type === "research_source") {
                        assistantMessage.research = upsertResearchSource(assistantMessage.research, event.source);
                        redrawAssistant();
                        return;
                    }

                    assistantMessage.content = typeof event.text === "string"
                        ? event.text
                        : assistantMessage.content + (event.delta || "");
                    assistantMessage.display_content = assistantMessage.content;
                    redrawAssistant();
                });

                if (streamError) {
                    throw new Error(streamError);
                }
            }

            assistantMessage.content = String(assistantMessage.content || "").trim();
            assistantMessage.display_content = assistantMessage.content;
            if (!assistantMessage.content) {
                assistantMessage.content = "A IA nao retornou conteudo.";
                assistantMessage.display_content = assistantMessage.content;
            }
            if (assistantMessage.research.length && /escrevendo resposta/i.test(assistantMessage.research_status)) {
                assistantMessage.research_status = "Pesquisa concluida.";
            }

            session.messages.push({ ...assistantMessage });
            session.updatedAt = new Date().toISOString();
            persistChatState();
            renderSidebar();
            renderMessages();
        } catch (error) {
            const message = error?.message || error?.error || String(error || "Erro desconhecido.");
            session.messages.push({
                role: "assistant",
                content: `Falha ao conversar com a IA: ${message}`,
                display_content: `Falha ao conversar com a IA: ${message}`,
                research: assistantMessage.research,
                research_queries: assistantMessage.research_queries,
                research_status: assistantMessage.research_status,
                research_collapsed: assistantMessage.research_collapsed,
            });
            session.updatedAt = new Date().toISOString();
            persistChatState();
            renderSidebar();
            renderMessages();
        } finally {
            chatSendBtn.disabled = false;
            scrollToBottom();
        }
    };

    const renderLlmCards = (data) => {
        if (!llmModelsContainer) return;

        llmModelsContainer.innerHTML = "";
        Object.entries(data.models || {}).forEach(([modelId, modelInfo]) => {
            const card = document.createElement("div");
            card.className = `llm-model-card${modelInfo.selected ? " active" : ""}`;

            let actionHtml = "";
            if (modelInfo.status === "ready" || modelInfo.status === "downloaded") {
                if (modelInfo.selected) {
                    actionHtml = `<button class="llm-model-card-btn btn-selected" disabled>Ativo</button>`;
                } else {
                    actionHtml = `<button class="llm-model-card-btn btn-select" onclick="selectModel('${modelId}')">Selecionar</button>`;
                }
            } else if (modelInfo.status === "downloading") {
                actionHtml = `<span style="font-size:0.78rem;color:#f59e0b;">${escapeHtml(modelInfo.progress || "Preparando...")}</span>`;
            } else {
                actionHtml = `<button class="llm-model-card-btn btn-download" onclick="downloadLLM('${modelId}')">Instalar</button>`;
            }

            card.innerHTML = `
                <div class="llm-model-card-info">
                    <div class="llm-model-card-name">${escapeHtml(modelInfo.title)}</div>
                    <div class="llm-model-card-size">${escapeHtml(modelInfo.description || modelInfo.size || "")}${modelInfo.progress ? ` - ${escapeHtml(modelInfo.progress)}` : ""}</div>
                </div>
                ${actionHtml}
            `;
            llmModelsContainer.appendChild(card);
        });
    };

    const applyLlmBadge = (data) => {
        if (!chatModelBadge) return;

        const selectedEntry = Object.values(data.models || {}).find((model) => model.selected);
        const label = selectedEntry?.title || data.engine_label || "Ollama local";
        const progress = selectedEntry?.status === "downloading" ? ` (${selectedEntry.progress || "Preparando"})` : "";
        chatModelBadge.innerHTML = `${escapeHtml(label + progress)} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`;
        chatModelBadge.title = data.notice || data.runtime_error || label;
    };

    window.fetchLlmStatus = async function fetchLlmStatusOverride() {
        if (llmStatusTimer) {
            clearTimeout(llmStatusTimer);
            llmStatusTimer = null;
        }

        if (!llmModelsContainer && !infoLlm && !chatModelBadge) return;

        try {
            const response = await fetch(`${apiBase}/api/llm/status`);
            if (!response.ok) return;

            const data = await response.json();
            const models = Object.values(data.models || {});
            const anyDownloading = models.some((model) => model.status === "downloading");

            if (infoLlm) {
                if (data.runtime_error) {
                    infoLlm.textContent = "Ollama offline";
                    infoLlm.title = data.runtime_error;
                } else {
                    infoLlm.textContent = data.engine_label || "Ollama online";
                    infoLlm.title = data.notice || "";
                }
            }

            applyLlmBadge(data);
            renderLlmCards(data);

            if (anyDownloading) {
                llmStatusTimer = setTimeout(() => {
                    window.fetchLlmStatus();
                }, 2000);
            }
        } catch (error) {
            if (infoLlm) {
                infoLlm.textContent = "Ollama indisponivel";
                infoLlm.title = error.message || "Falha ao consultar status.";
            }
        }
    };

    const resetActiveChat = () => {
        chatSessions = chatSessions.filter((session) => session.messages.length);
        const freshSession = {
            id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            title: "Novo chat",
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            messages: [],
        };
        chatSessions.unshift(freshSession);
        activeChatId = freshSession.id;
        pendingAttachments = [];
        if (chatInput) chatInput.value = "";
        renderPendingAttachments();
        persistChatState();
        renderSidebar();
        renderMessages();
        chatInput?.focus();
        notify("Novo chat criado.", "success");
    };

    window.lyraCreateNewChat = resetActiveChat;

    chatAttachBtn?.addEventListener("click", () => chatFileInput?.click());
    chatFileInput?.addEventListener("change", (event) => {
        handleSelectedFiles(event.target.files);
    });
    chatSendBtn?.addEventListener("click", () => sendChatMessage(chatInput.value));
    chatInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendChatMessage(chatInput.value);
        }
    });
    chatNewBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        resetActiveChat();
    });
    chatWebToggle?.addEventListener("click", () => {
        webSearchEnabled = !webSearchEnabled;
        localStorage.setItem(CHAT_WEB_SEARCH_KEY, webSearchEnabled ? "1" : "0");
        updateWebToggleUi();
        notify(
            webSearchEnabled ? "Pesquisa web ativada no chat." : "Pesquisa web desativada no chat.",
            "info"
        );
    });
    chatWebDepth?.addEventListener("change", () => {
        webSearchLevel = String(chatWebDepth.value || "basic").trim().toLowerCase();
        localStorage.setItem(CHAT_WEB_SEARCH_LEVEL_KEY, webSearchLevel);
        updateWebDepthUi();
        notify(`Profundidade da pesquisa: ${chatWebDepth.options[chatWebDepth.selectedIndex]?.text || webSearchLevel}.`, "info");
    });
    chatSearchHint?.addEventListener("click", () => notify("O historico do chat fica salvo localmente neste navegador.", "info"));
    chatContextHint?.addEventListener("click", () => notify("Peca blocos como title, style, lyrics e duration para exportar melhor. Com a pesquisa web ativa, o chat tambem resume fontes em tempo real.", "info"));
    suggestionButtons.forEach((button) => {
        button?.addEventListener("click", () => {
            const prompt = button.getAttribute("data-prompt");
            if (!prompt) return;
            if (chatInput) chatInput.value = prompt;
            sendChatMessage(prompt);
        });
    });

    loadChatState();
    persistChatState();
    renderPendingAttachments();
    renderSidebar();
    renderMessages();
    updateWebToggleUi();
    updateWebDepthUi();
    window.fetchLlmStatus?.();
});
