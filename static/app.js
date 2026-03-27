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
const karaokeDisplay = document.getElementById('karaoke-display');
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
let wordTimings = [];  // [{word, start, end}, ...]
let karaokeAnimFrame = null;

// ===== File Formatting =====
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
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        selectFile(files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        selectFile(fileInput.files[0]);
    }
});

// ===== File Selection =====
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

// ===== Generate Button =====
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

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

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
    if (eventSource) {
        eventSource.close();
    }

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
        showError('Connection to server lost. Please try again.');
    };
}

// ===== Progress UI Updates =====
function resetProgress() {
    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    progressStage.textContent = 'Starting...';

    document.querySelectorAll('.stage').forEach((s) => {
        s.classList.remove('active', 'done');
    });
    document.querySelectorAll('.stage-line').forEach((l) => {
        l.classList.remove('done');
    });
}

function updateProgress(data) {
    const { status, progress, stage } = data;

    progressFill.style.width = progress + '%';
    progressText.textContent = progress + '%';
    progressStage.textContent = stage || status;

    const stageOrder = ['extracting', 'transcribing', 'formatting'];
    const currentIdx = stageOrder.indexOf(status);

    const stages = document.querySelectorAll('.stage');
    const lines = document.querySelectorAll('.stage-line');

    stages.forEach((s, i) => {
        s.classList.remove('active', 'done');
        if (i < currentIdx) {
            s.classList.add('done');
        } else if (i === currentIdx) {
            s.classList.add('active');
        }
    });

    lines.forEach((l, i) => {
        l.classList.remove('done');
        if (i < currentIdx) {
            l.classList.add('done');
        }
    });
}

// ===== Transcription Complete =====
async function onTranscriptionComplete(jobId) {
    progressSection.classList.add('hidden');

    try {
        const response = await fetch(`/api/preview/${jobId}`);
        if (!response.ok) throw new Error('Failed to load preview');

        const data = await response.json();

        // Render SRT preview
        renderSrtPreview(data.srt_content);
        srtFilename.textContent = data.filename.replace(/\.[^.]+$/, '.srt');

        // Setup karaoke with word timings
        wordTimings = data.words || [];
        initKaraoke();

        // Setup audio player
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
function initKaraoke() {
    if (wordTimings.length === 0) {
        karaokeText.textContent = 'No word data available';
        return;
    }

    // Build all words as spans
    karaokeText.innerHTML = '';
    wordTimings.forEach((w, i) => {
        const span = document.createElement('span');
        span.className = 'karaoke-word';
        span.textContent = w.word;
        span.dataset.index = i;
        karaokeText.appendChild(span);

        // Add space between words
        if (i < wordTimings.length - 1) {
            karaokeText.appendChild(document.createTextNode(' '));
        }
    });
}

function startKaraokeLoop() {
    const wordSpans = karaokeText.querySelectorAll('.karaoke-word');
    if (wordSpans.length === 0) return;

    // How many words to show at once (a "window" around current word)
    const WINDOW_SIZE = 8;

    function tick() {
        const currentTime = audioElement.currentTime;

        // Find current word index
        let activeIdx = -1;
        for (let i = 0; i < wordTimings.length; i++) {
            if (currentTime >= wordTimings[i].start && currentTime < wordTimings[i].end) {
                activeIdx = i;
                break;
            }
            // Between words — still show last spoken word as active
            if (i < wordTimings.length - 1 &&
                currentTime >= wordTimings[i].end &&
                currentTime < wordTimings[i + 1].start) {
                activeIdx = i;
                break;
            }
        }

        // Calculate visible window
        const windowStart = Math.max(0, activeIdx - Math.floor(WINDOW_SIZE / 3));
        const windowEnd = Math.min(wordTimings.length - 1, windowStart + WINDOW_SIZE - 1);

        wordSpans.forEach((span, i) => {
            span.classList.remove('active', 'spoken');

            // Hide words outside the window
            if (i < windowStart || i > windowEnd) {
                span.style.display = 'none';
                // Also hide the text node (space) after this span
                if (span.nextSibling && span.nextSibling.nodeType === 3) {
                    span.nextSibling.textContent = '';
                }
            } else {
                span.style.display = 'inline';
                if (span.nextSibling && span.nextSibling.nodeType === 3 && i < windowEnd) {
                    span.nextSibling.textContent = ' ';
                }

                if (i < activeIdx) {
                    span.classList.add('spoken');
                } else if (i === activeIdx) {
                    span.classList.add('active');
                }
            }
        });

        // Update timeline
        if (audioElement.duration) {
            const pct = (currentTime / audioElement.duration) * 100;
            timelineProgress.style.width = pct + '%';
            timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(audioElement.duration)}`;
        }

        if (!audioElement.paused) {
            karaokeAnimFrame = requestAnimationFrame(tick);
        }
    }

    karaokeAnimFrame = requestAnimationFrame(tick);
}

function stopKaraoke() {
    if (karaokeAnimFrame) {
        cancelAnimationFrame(karaokeAnimFrame);
        karaokeAnimFrame = null;
    }
    audioElement.pause();
    audioElement.currentTime = 0;
    updatePlayPauseIcon(false);
}

function updatePlayPauseIcon(isPlaying) {
    playIcon.classList.toggle('hidden', isPlaying);
    pauseIcon.classList.toggle('hidden', !isPlaying);
}

// ===== Audio Player Controls =====
playBtn.addEventListener('click', () => {
    if (audioElement.paused) {
        audioElement.play();
    } else {
        audioElement.pause();
    }
});

audioElement.addEventListener('play', () => {
    updatePlayPauseIcon(true);
    startKaraokeLoop();
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

// Timeline seeking
timelineContainer.addEventListener('click', (e) => {
    if (!audioElement.duration) return;
    const rect = timelineContainer.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioElement.currentTime = pct * audioElement.duration;

    // Update display immediately
    const currentTime = audioElement.currentTime;
    timelineProgress.style.width = (pct * 100) + '%';
    timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(audioElement.duration)}`;

    // If playing, the loop will continue. If paused, do one tick.
    if (audioElement.paused) {
        startKaraokeLoop();
        // Single frame update then stop
        setTimeout(() => {
            if (audioElement.paused && karaokeAnimFrame) {
                cancelAnimationFrame(karaokeAnimFrame);
                karaokeAnimFrame = null;
            }
        }, 50);
    }
});

// ===== SRT Preview with Syntax Highlighting =====
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

// ===== Download =====
downloadBtn.addEventListener('click', () => {
    if (!currentJobId) return;
    window.location.href = `/api/download/${currentJobId}`;
});

// ===== New File =====
newFileBtn.addEventListener('click', () => {
    stopKaraoke();
    selectedFile = null;
    fileInput.value = '';
    currentJobId = null;
    wordTimings = [];

    fileInfo.classList.add('hidden');
    dropzone.classList.remove('hidden');
    resultSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    errorSection.classList.add('hidden');
    generateBtn.disabled = true;
    resetGenerateBtn();
});

// ===== Error Handling =====
function showError(message) {
    progressSection.classList.add('hidden');
    errorSection.classList.remove('hidden');
    errorMessage.textContent = message;
    resetGenerateBtn();
}

errorRetry.addEventListener('click', () => {
    errorSection.classList.add('hidden');
    if (selectedFile) {
        generateBtn.disabled = false;
    }
});

// ===== Reset Generate Button =====
function resetGenerateBtn() {
    generateBtn.innerHTML = `
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        Generate Subtitles
    `;
    generateBtn.disabled = !selectedFile;
}
