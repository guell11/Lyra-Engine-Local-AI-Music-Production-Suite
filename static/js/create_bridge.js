document.addEventListener("DOMContentLoaded", () => {
    const captionInput = document.getElementById("caption-input");
    const lyricsInput = document.getElementById("lyrics-input");
    const durationInput = document.getElementById("opt-duration");
    const languageSelect = document.getElementById("language-select");
    const songTitleInput = document.getElementById("song-title");
    const bpmInput = document.getElementById("opt-bpm");
    const aiPromptInput = document.getElementById("ai-prompt-input");

    if (!captionInput && !lyricsInput && !durationInput && !languageSelect && !songTitleInput && !bpmInput && !aiPromptInput) {
        return;
    }

    const STORAGE_KEY = "lyra_create_draft_v1";

    const trigger = (element, eventName) => {
        if (!element) return;
        element.dispatchEvent(new Event(eventName, { bubbles: true }));
    };

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

    const applyPayload = (payload, removeStored = false) => {
        if (!payload || typeof payload !== "object") return;
        if (captionInput && payload.caption) {
            captionInput.value = payload.caption;
            trigger(captionInput, "input");
        }
        if (lyricsInput && payload.lyrics) {
            lyricsInput.value = payload.lyrics;
            trigger(lyricsInput, "input");
        }
        if (durationInput && payload.duration) {
            durationInput.value = payload.duration;
            trigger(durationInput, "input");
            trigger(durationInput, "change");
        }
        if (languageSelect && payload.language) {
            languageSelect.value = normalizeLanguage(payload.language);
            trigger(languageSelect, "change");
        }
        if (songTitleInput && payload.title) {
            songTitleInput.value = payload.title;
            trigger(songTitleInput, "input");
        }
        if (bpmInput && payload.bpm) {
            bpmInput.value = payload.bpm;
            trigger(bpmInput, "input");
            trigger(bpmInput, "change");
        }
        if (aiPromptInput && payload.ai_prompt) {
            aiPromptInput.value = payload.ai_prompt;
            trigger(aiPromptInput, "input");
        }

        if (typeof showToast === "function") {
            showToast("Rascunho importado do chat.", "success");
        }
        if (removeStored) {
            localStorage.removeItem(STORAGE_KEY);
        }
    };

    const applyDraft = () => {
        let payload = null;
        try {
            payload = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
        } catch (error) {
            console.warn("Falha ao ler draft da aba Criar", error);
            return;
        }

        applyPayload(payload, true);
    };

    applyDraft();
    setTimeout(applyDraft, 500);
    setTimeout(applyDraft, 1500);

    window.addEventListener("lyra:create-draft", (event) => {
        applyPayload(event.detail, false);
    });
});
