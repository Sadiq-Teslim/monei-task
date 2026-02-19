const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const DOM = {
    chatArea: $("#chatArea"),
    messages: $("#messages"),
    welcomeScreen: $("#welcomeScreen"),
    micBtn: $("#micBtn"),
    micIcon: $("#micIcon"),
    micRipple: $("#micRipple"),
    micContainer: $(".mic-container"),
    statusBar: $("#statusBar"),
    statusText: $("#statusText"),
    voiceSelect: $("#voiceSelect"),
    clearChat: $("#clearChat"),
    keyboardBtn: $("#keyboardBtn"),
    textInputBar: $("#textInputBar"),
    textInput: $("#textInput"),
    sendBtn: $("#sendBtn"),
    toastContainer: $("#toastContainer"),
};

const State = {
    recording: false,
    processing: false,
    mediaRecorder: null,
    audioChunks: [],
    currentAudio: null,
    typingMode: false,
};

(async function init() {
    await loadVoices();
    bindEvents();
})();

async function loadVoices() {
    try {
        const res = await fetch("/api/voices");
        const data = await res.json();
        DOM.voiceSelect.innerHTML = "";
        data.voices.forEach((v) => {
            const opt = document.createElement("option");
            opt.value = v.name;
            opt.textContent = v.name;
            DOM.voiceSelect.appendChild(opt);
        });
    } catch {
        toast("Failed to load voices", "error");
    }
}

function bindEvents() {
    DOM.micBtn.addEventListener("click", toggleRecording);
    DOM.clearChat.addEventListener("click", clearConversation);
    DOM.keyboardBtn.addEventListener("click", toggleTypingMode);
    DOM.sendBtn.addEventListener("click", sendTextMessage);
    DOM.textInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage();
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.code === "Space" && !State.typingMode && document.activeElement !== DOM.textInput) {
            e.preventDefault();
            toggleRecording();
        }
    });
}

async function toggleRecording() {
    if (State.processing) return;
    State.recording ? stopRecording() : startRecording();
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        State.audioChunks = [];

        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm";

        State.mediaRecorder = new MediaRecorder(stream, { mimeType });

        State.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) State.audioChunks.push(e.data);
        };

        State.mediaRecorder.onstop = () => {
            stream.getTracks().forEach((t) => t.stop());
            const blob = new Blob(State.audioChunks, { type: mimeType });
            handleRecordedAudio(blob);
        };

        State.mediaRecorder.start(250);
        State.recording = true;
        setStatus("recording", "Listening...");
        DOM.micBtn.classList.add("recording");
        DOM.micContainer.classList.add("active");
    } catch {
        toast("Microphone access denied", "error");
    }
}

function stopRecording() {
    if (!State.mediaRecorder || State.mediaRecorder.state === "inactive") return;
    State.mediaRecorder.stop();
    State.recording = false;
    DOM.micBtn.classList.remove("recording");
    DOM.micContainer.classList.remove("active");
}

async function handleRecordedAudio(blob) {
    setStatus("processing", "Processing...");
    DOM.micBtn.classList.add("disabled");
    State.processing = true;

    hideWelcome();

    const thinkingId = addThinking();
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");

    try {
        const voice = DOM.voiceSelect.value || "Idera";
        const res = await fetch(`/api/chat?voice=${encodeURIComponent(voice)}`, {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Request failed");
        }

        const data = await res.json();
        removeThinking(thinkingId);
        addMessage("user", data.user_text);
        addMessage("ai", data.ai_text, data.audio_url);
        playAudio(data.audio_url);
    } catch (e) {
        removeThinking(thinkingId);
        toast(e.message || "Something went wrong", "error");
    } finally {
        State.processing = false;
        DOM.micBtn.classList.remove("disabled");
        setStatus("idle", "Ready");
    }
}

async function sendTextMessage() {
    const text = DOM.textInput.value.trim();
    if (!text || State.processing) return;

    DOM.textInput.value = "";
    hideWelcome();
    addMessage("user", text);

    setStatus("processing", "Processing...");
    DOM.micBtn.classList.add("disabled");
    State.processing = true;

    const thinkingId = addThinking();

    try {
        const voice = DOM.voiceSelect.value || "Idera";
        const res = await fetch("/api/chat/text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, voice }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Request failed");
        }

        const data = await res.json();
        removeThinking(thinkingId);
        addMessage("ai", data.ai_text, data.audio_url);
        playAudio(data.audio_url);
    } catch (e) {
        removeThinking(thinkingId);
        toast(e.message || "Something went wrong", "error");
    } finally {
        State.processing = false;
        DOM.micBtn.classList.remove("disabled");
        setStatus("idle", "Ready");
    }
}

function hideWelcome() {
    if (!DOM.welcomeScreen.classList.contains("hidden")) {
        DOM.welcomeScreen.classList.add("hidden");
    }
}

function addMessage(role, text, audioUrl, isObjectUrl) {
    const now = new Date();
    const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const iconName = role === "user" ? "person" : "neurology";

    const wrapper = document.createElement("div");
    wrapper.className = `msg msg-${role}`;

    let audioHtml = "";
    if (audioUrl) {
        audioHtml = `
        <div class="msg-audio" data-src="${audioUrl}" ${isObjectUrl ? 'data-objurl="1"' : ""}>
            <button class="audio-play-btn" aria-label="Play audio">
                <span class="material-symbols-rounded">play_arrow</span>
            </button>
            <div class="audio-wave-vis">
                ${Array(8).fill('<span></span>').join("")}
            </div>
            <span class="audio-time">0:00</span>
        </div>`;
    }

    wrapper.innerHTML = `
        <div class="msg-avatar">
            <span class="material-symbols-rounded">${iconName}</span>
        </div>
        <div class="msg-body">
            <div class="msg-bubble">${role === "ai" ? formatMarkdown(text) : escapeHtml(text)}</div>
            ${audioHtml}
            <div class="msg-time">${time}</div>
        </div>`;

    DOM.messages.appendChild(wrapper);
    scrollToBottom();

    const playBtn = wrapper.querySelector(".audio-play-btn");
    if (playBtn) {
        const audioEl = wrapper.querySelector(".msg-audio");
        playBtn.addEventListener("click", () => toggleAudioPlayback(audioEl));
    }
}

function addThinking() {
    const id = "thinking-" + Date.now();
    const el = document.createElement("div");
    el.className = "msg msg-ai msg-thinking";
    el.id = id;
    el.innerHTML = `
        <div class="msg-avatar">
            <span class="material-symbols-rounded">neurology</span>
        </div>
        <div class="msg-body">
            <div class="msg-bubble">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
        </div>`;
    DOM.messages.appendChild(el);
    scrollToBottom();
    return id;
}

function removeThinking(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function toggleAudioPlayback(audioEl) {
    const src = audioEl.dataset.src;
    const btn = audioEl.querySelector(".audio-play-btn .material-symbols-rounded");
    const waveVis = audioEl.querySelector(".audio-wave-vis");
    const timeEl = audioEl.querySelector(".audio-time");

    if (State.currentAudio && !State.currentAudio.paused) {
        State.currentAudio.pause();
        State.currentAudio.currentTime = 0;
        resetAllAudioUI();

        if (State.currentAudio._src === src) {
            State.currentAudio = null;
            return;
        }
    }

    const audio = new Audio(src);
    audio._src = src;
    State.currentAudio = audio;

    btn.textContent = "pause";
    waveVis.classList.add("playing");
    setStatus("speaking", "Speaking...");

    audio.ontimeupdate = () => {
        const cur = formatTime(audio.currentTime);
        timeEl.textContent = cur;
    };

    audio.onended = () => {
        btn.textContent = "play_arrow";
        waveVis.classList.remove("playing");
        timeEl.textContent = formatTime(audio.duration || 0);
        setStatus("idle", "Ready");
        State.currentAudio = null;
    };

    audio.onerror = () => {
        btn.textContent = "play_arrow";
        waveVis.classList.remove("playing");
        setStatus("idle", "Ready");
        toast("Failed to play audio", "error");
        State.currentAudio = null;
    };

    audio.play();
}

function playAudio(url) {
    if (State.currentAudio && !State.currentAudio.paused) {
        State.currentAudio.pause();
        resetAllAudioUI();
    }

    const audio = new Audio(url);
    audio._src = url;
    State.currentAudio = audio;
    setStatus("speaking", "Speaking...");

    const matchingEl = DOM.messages.querySelector(`.msg-audio[data-src="${CSS.escape(url)}"]`);
    if (matchingEl) {
        const btn = matchingEl.querySelector(".audio-play-btn .material-symbols-rounded");
        const waveVis = matchingEl.querySelector(".audio-wave-vis");
        const timeEl = matchingEl.querySelector(".audio-time");

        btn.textContent = "pause";
        waveVis.classList.add("playing");

        audio.ontimeupdate = () => {
            timeEl.textContent = formatTime(audio.currentTime);
        };

        audio.onended = () => {
            btn.textContent = "play_arrow";
            waveVis.classList.remove("playing");
            timeEl.textContent = formatTime(audio.duration || 0);
            setStatus("idle", "Ready");
            State.currentAudio = null;
        };
    } else {
        audio.onended = () => {
            setStatus("idle", "Ready");
            State.currentAudio = null;
        };
    }

    audio.onerror = () => {
        resetAllAudioUI();
        setStatus("idle", "Ready");
        State.currentAudio = null;
    };

    audio.play().catch(() => {});
}

function resetAllAudioUI() {
    DOM.messages.querySelectorAll(".msg-audio").forEach((el) => {
        el.querySelector(".audio-play-btn .material-symbols-rounded").textContent = "play_arrow";
        el.querySelector(".audio-wave-vis").classList.remove("playing");
    });
}

function clearConversation() {
    DOM.messages.innerHTML = "";
    DOM.welcomeScreen.classList.remove("hidden");

    if (State.currentAudio && !State.currentAudio.paused) {
        State.currentAudio.pause();
    }
    State.currentAudio = null;
    setStatus("idle", "Ready");
}

function toggleTypingMode() {
    State.typingMode = !State.typingMode;
    DOM.textInputBar.classList.toggle("hidden", !State.typingMode);

    const label = DOM.keyboardBtn.querySelector("span:last-child");
    if (State.typingMode) {
        label.textContent = "Voice";
        DOM.keyboardBtn.querySelector(".material-symbols-rounded").textContent = "mic";
        DOM.textInput.focus();
    } else {
        label.textContent = "Type";
        DOM.keyboardBtn.querySelector(".material-symbols-rounded").textContent = "keyboard";
    }
}

function setStatus(state, text) {
    DOM.statusBar.className = "status-bar";
    if (state !== "idle") DOM.statusBar.classList.add(state);
    DOM.statusText.textContent = text;
}

function toast(message, type = "info") {
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    const icon = type === "error" ? "error" : type === "success" ? "check_circle" : "info";
    el.innerHTML = `<span class="material-symbols-rounded">${icon}</span><span>${escapeHtml(message)}</span>`;
    DOM.toastContainer.appendChild(el);

    setTimeout(() => {
        el.classList.add("removing");
        el.addEventListener("animationend", () => el.remove());
    }, 4000);
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        DOM.chatArea.scrollTop = DOM.chatArea.scrollHeight;
    });
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatMarkdown(raw) {
    let text = escapeHtml(raw);

    // Headings: ### heading
    text = text.replace(/^### (.+)$/gm, '<strong class="md-h3">$1</strong>');
    text = text.replace(/^## (.+)$/gm, '<strong class="md-h2">$1</strong>');

    // Bold: **text**
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Unordered list items: - item
    text = text.replace(/^- (.+)$/gm, '<span class="md-li">&bull; $1</span>');

    // Ordered list items: 1. item
    text = text.replace(/^\d+\.\s+(.+)$/gm, '<span class="md-li">$1</span>');

    // Line breaks
    text = text.replace(/\n/g, "<br>");

    // Clean up excessive <br> runs
    text = text.replace(/(<br>){3,}/g, "<br><br>");

    return text;
}
