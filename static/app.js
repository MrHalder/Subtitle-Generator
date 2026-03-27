// ===== DOM Elements =====
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const fileRemove = document.getElementById('file-remove');
const generateBtn = document.getElementById('generate-btn');
const uploadSection = document.getElementById('upload-section');
const progressSection = document.getElementById('progress-section');
const errorSection = document.getElementById('error-section');
const errorMessage = document.getElementById('error-message');
const errorRetry = document.getElementById('error-retry');
const resultSection = document.getElementById('result-section');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const progressStage = document.getElementById('progress-stage');
const srtPreview = document.querySelector('#srt-preview code');
const srtFilename = document.getElementById('srt-filename');
const downloadBtn = document.getElementById('download-btn');
const newFileBtn = document.getElementById('new-file-btn');
const langPills = document.querySelectorAll('.lang-pill');

// Karaoke / Audio elements
const karaokeText = document.getElementById('karaoke-text');
const audioElement = document.getElementById('audio-element');
const playBtn = document.getElementById('play-btn');
const playIcon = document.getElementById('play-icon');
const pauseIcon = document.getElementById('pause-icon');
const timelineContainer = document.getElementById('timeline-container');
const timelineProgress = document.getElementById('timeline-progress');
const timeDisplay = document.getElementById('time-display');

// ===== State =====
let selectedFile = null;
let selectedLanguage = 'en';
let currentJobId = null;
let eventSource = null;

// Karaoke state
let wordTimings = [];       // [{word, start, end}, ...]
let subtitleChunks = [];    // [{words: [{word, start, end}], start, end}, ...]
let karaokeAnimFrame = null;
let currentChunkIdx = -1;

const WORDS_PER_CHUNK = 4;

// ===== Utilities =====
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ===== Dropzone Events =====
dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
    }
});

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
});

dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('drag-over');
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
        selectFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) selectFile(fileInput.files[0]);
});

function selectFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    fileInfo.classList.remove('hidden');
    dropzone.classList.add('hidden');
    generateBtn.disabled = false;
}

fileRemove.addEventListener('click', () => {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.classList.add('hidden');
    dropzone.classList.remove('hidden');
    generateBtn.disabled = true;
});

// ===== Language Selection =====
langPills.forEach((pill) => {
    pill.addEventListener('click', () => {
        langPills.forEach((p) => {
            p.classList.remove('active');
            p.setAttribute('aria-checked', 'false');
        });
        pill.classList.add('active');
        pill.setAttribute('aria-checked', 'true');
        selectedLanguage = pill.dataset.lang;
    });
});

// ===== Generate =====
generateBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<div class="spinner"></div> Processing...';
    progressSection.classList.remove('hidden');
    errorSection.classList.add('hidden');
    resultSection.classList.add('hidden');
    resetProgress();
    stopKaraoke();

    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('language', selectedLanguage);

        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await response.json();
        currentJobId = data.job_id;
        startProgressStream(currentJobId);
    } catch (err) {
        showError(err.message);
    }
});

// ===== Progress SSE =====
function startProgressStream(jobId) {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`/api/progress/${jobId}`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);

        if (data.status === 'complete') {
            eventSource.close();
            eventSource = null;
            onTranscriptionComplete(jobId);
        } else if (data.status === 'error') {
            eventSource.close();
            eventSource = null;
            showError(data.error || 'Transcription failed');
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
        eventSource = null;
        showError('Connection to server lost.');
    };
}

function resetProgress() {
    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    progressStage.textContent = 'Starting...';
    document.querySelectorAll('.stage').forEach((s) => s.classList.remove('active', 'done'));
    document.querySelectorAll('.stage-line').forEach((l) => l.classList.remove('done'));
}

function updateProgress(data) {
    const { status, progress, stage } = data;
    progressFill.style.width = progress + '%';
    progressText.textContent = progress + '%';
    progressStage.textContent = stage || status;

    const stageOrder = ['extracting', 'transcribing', 'formatting'];
    const currentIdx = stageOrder.indexOf(status);
    document.querySelectorAll('.stage').forEach((s, i) => {
        s.classList.remove('active', 'done');
        if (i < currentIdx) s.classList.add('done');
        else if (i === currentIdx) s.classList.add('active');
    });
    document.querySelectorAll('.stage-line').forEach((l, i) => {
        l.classList.remove('done');
        if (i < currentIdx) l.classList.add('done');
    });
}

// ===== Transcription Complete =====
async function onTranscriptionComplete(jobId) {
    progressSection.classList.add('hidden');

    try {
        const response = await fetch(`/api/preview/${jobId}`);
        if (!response.ok) throw new Error('Failed to load preview');
        const data = await response.json();

        renderSrtPreview(data.srt_content);
        srtFilename.textContent = data.filename.replace(/\.[^.]+$/, '.srt');

        // Build karaoke data
        wordTimings = data.words || [];
        buildSubtitleChunks();
        renderChunk(-1); // Show first chunk idle

        if (data.has_audio) {
            audioElement.src = `/api/audio/${jobId}`;
            audioElement.load();
        }

        resultSection.classList.remove('hidden');
        resetGenerateBtn();
    } catch (err) {
        showError(err.message);
    }
}

// ===== Karaoke Engine =====

/**
 * Group words into subtitle-sized chunks (matching SRT output).
 * Each chunk = one subtitle line shown on screen at a time.
 */
function buildSubtitleChunks() {
    subtitleChunks = [];
    for (let i = 0; i < wordTimings.length; i += WORDS_PER_CHUNK) {
        const chunkWords = wordTimings.slice(i, i + WORDS_PER_CHUNK);
        if (chunkWords.length === 0) continue;
        subtitleChunks.push({
            words: chunkWords,
            start: chunkWords[0].start,
            end: chunkWords[chunkWords.length - 1].end,
        });
    }
}

/**
 * Render a specific chunk on the karaoke display.
 * All words shown; styling determines which is active/spoken/upcoming.
 */
function renderChunk(chunkIdx) {
    if (chunkIdx === currentChunkIdx) return; // already rendered
    currentChunkIdx = chunkIdx;

    // Before first chunk or after last
    if (chunkIdx < 0 || chunkIdx >= subtitleChunks.length) {
        if (subtitleChunks.length > 0) {
            // Show first chunk in idle state
            renderChunkWords(subtitleChunks[0], -1);
        } else {
            karaokeText.textContent = 'No subtitles';
        }
        return;
    }

    renderChunkWords(subtitleChunks[chunkIdx], -1);
}

/**
 * Render the words of a chunk, with activeWordIdx highlighted.
 * -1 = no word active (all upcoming), words < activeWordIdx = spoken.
 */
function renderChunkWords(chunk, activeWordIdx) {
    karaokeText.innerHTML = '';
    chunk.words.forEach((w, i) => {
        const span = document.createElement('span');
        span.className = 'karaoke-word';
        span.textContent = w.word;
        span.dataset.idx = i;

        if (i < activeWordIdx) {
            span.classList.add('spoken');
        } else if (i === activeWordIdx) {
            span.classList.add('active');
        }
        // else: upcoming (default dim state)

        karaokeText.appendChild(span);

        if (i < chunk.words.length - 1) {
            karaokeText.appendChild(document.createTextNode(' '));
        }
    });
}

/**
 * Main karaoke tick — called on each animation frame during playback.
 */
function karaokeTick() {
    const t = audioElement.currentTime;

    // Find which chunk we're in
    let chunkIdx = -1;
    for (let i = 0; i < subtitleChunks.length; i++) {
        if (t >= subtitleChunks[i].start && t < subtitleChunks[i].end) {
            chunkIdx = i;
            break;
        }
        // Between chunks — show next chunk
        if (i < subtitleChunks.length - 1 &&
            t >= subtitleChunks[i].end && t < subtitleChunks[i + 1].start) {
            chunkIdx = i + 1;
            break;
        }
    }
    // Past last chunk
    if (chunkIdx === -1 && subtitleChunks.length > 0) {
        if (t >= subtitleChunks[subtitleChunks.length - 1].end) {
            chunkIdx = subtitleChunks.length; // past end
        } else if (t < subtitleChunks[0].start) {
            chunkIdx = 0; // before start
        }
    }

    // Switch chunk if needed (re-render DOM)
    if (chunkIdx !== currentChunkIdx && chunkIdx >= 0 && chunkIdx < subtitleChunks.length) {
        currentChunkIdx = chunkIdx;
        renderChunkWords(subtitleChunks[chunkIdx], -1);
    }

    // Update word highlighting within current chunk (no DOM rebuild, just class toggle)
    if (currentChunkIdx >= 0 && currentChunkIdx < subtitleChunks.length) {
        const chunk = subtitleChunks[currentChunkIdx];
        const wordSpans = karaokeText.querySelectorAll('.karaoke-word');

        let activeIdx = -1;
        for (let i = 0; i < chunk.words.length; i++) {
            if (t >= chunk.words[i].start && t < chunk.words[i].end) {
                activeIdx = i;
                break;
            }
            // Between words in same chunk
            if (i < chunk.words.length - 1 &&
                t >= chunk.words[i].end && t < chunk.words[i + 1].start) {
                activeIdx = i;
                break;
            }
        }
        // Past last word in chunk
        if (activeIdx === -1 && chunk.words.length > 0 && t >= chunk.words[chunk.words.length - 1].start) {
            activeIdx = chunk.words.length - 1;
        }

        wordSpans.forEach((span, i) => {
            span.classList.remove('active', 'spoken');
            if (i < activeIdx) {
                span.classList.add('spoken');
            } else if (i === activeIdx) {
                span.classList.add('active');
            }
        });
    }

    // Update timeline
    if (audioElement.duration) {
        timelineProgress.style.width = (t / audioElement.duration * 100) + '%';
        timeDisplay.textContent = `${formatTime(t)} / ${formatTime(audioElement.duration)}`;
    }

    if (!audioElement.paused) {
        karaokeAnimFrame = requestAnimationFrame(karaokeTick);
    }
}

function stopKaraoke() {
    if (karaokeAnimFrame) {
        cancelAnimationFrame(karaokeAnimFrame);
        karaokeAnimFrame = null;
    }
    audioElement.pause();
    audioElement.currentTime = 0;
    currentChunkIdx = -1;
    updatePlayPauseIcon(false);
}

function updatePlayPauseIcon(isPlaying) {
    playIcon.classList.toggle('hidden', isPlaying);
    pauseIcon.classList.toggle('hidden', !isPlaying);
}

// ===== Audio Controls =====
playBtn.addEventListener('click', () => {
    if (audioElement.paused) audioElement.play();
    else audioElement.pause();
});

audioElement.addEventListener('play', () => {
    updatePlayPauseIcon(true);
    currentChunkIdx = -1; // force re-render on next tick
    karaokeAnimFrame = requestAnimationFrame(karaokeTick);
});

audioElement.addEventListener('pause', () => {
    updatePlayPauseIcon(false);
    if (karaokeAnimFrame) {
        cancelAnimationFrame(karaokeAnimFrame);
        karaokeAnimFrame = null;
    }
});

audioElement.addEventListener('ended', () => {
    updatePlayPauseIcon(false);
    timelineProgress.style.width = '100%';
    if (karaokeAnimFrame) {
        cancelAnimationFrame(karaokeAnimFrame);
        karaokeAnimFrame = null;
    }
});

audioElement.addEventListener('loadedmetadata', () => {
    timeDisplay.textContent = `0:00 / ${formatTime(audioElement.duration)}`;
});

// Seek on timeline click
timelineContainer.addEventListener('click', (e) => {
    if (!audioElement.duration) return;
    const rect = timelineContainer.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioElement.currentTime = pct * audioElement.duration;
    timelineProgress.style.width = (pct * 100) + '%';
    timeDisplay.textContent = `${formatTime(audioElement.currentTime)} / ${formatTime(audioElement.duration)}`;

    // Force chunk re-render
    currentChunkIdx = -1;
    if (audioElement.paused) {
        karaokeAnimFrame = requestAnimationFrame(karaokeTick);
        setTimeout(() => {
            if (audioElement.paused && karaokeAnimFrame) {
                cancelAnimationFrame(karaokeAnimFrame);
                karaokeAnimFrame = null;
            }
        }, 50);
    }
});

// ===== SRT Preview =====
function renderSrtPreview(content) {
    const lines = content.split('\n');
    let html = '';
    for (const line of lines) {
        const trimmed = line.trim();
        if (/^\d+$/.test(trimmed)) {
            html += `<span class="srt-index">${escapeHtml(line)}</span>\n`;
        } else if (/\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}/.test(trimmed)) {
            html += `<span class="srt-timestamp">${escapeHtml(line)}</span>\n`;
        } else if (trimmed === '') {
            html += '\n';
        } else {
            html += `<span class="srt-text">${escapeHtml(line)}</span>\n`;
        }
    }
    srtPreview.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== Download / New File =====
downloadBtn.addEventListener('click', () => {
    if (currentJobId) window.location.href = `/api/download/${currentJobId}`;
});

newFileBtn.addEventListener('click', () => {
    stopKaraoke();
    selectedFile = null;
    fileInput.value = '';
    currentJobId = null;
    wordTimings = [];
    subtitleChunks = [];
    fileInfo.classList.add('hidden');
    dropzone.classList.remove('hidden');
    resultSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    errorSection.classList.add('hidden');
    generateBtn.disabled = true;
    resetGenerateBtn();
});

// ===== Error =====
function showError(message) {
    progressSection.classList.add('hidden');
    errorSection.classList.remove('hidden');
    errorMessage.textContent = message;
    resetGenerateBtn();
}

errorRetry.addEventListener('click', () => {
    errorSection.classList.add('hidden');
    if (selectedFile) generateBtn.disabled = false;
});

function resetGenerateBtn() {
    generateBtn.innerHTML = `
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        Generate Subtitles
    `;
    generateBtn.disabled = !selectedFile;
}
