# Subtitle Generator

A local web app that generates accurate SRT subtitles from audio and video files using OpenAI's Whisper model, optimized for Apple Silicon.

## Features

- **Speech-to-text** powered by `mlx-whisper` (Apple Silicon optimized, 30-40% faster than whisper.cpp)
- **Language support**: English, Hindi, and Hinglish (code-mixed Hindi-English)
- **Karaoke preview**: Words highlight in real-time as audio plays back
- **Short subtitle chunks**: 3-5 words per subtitle with precise word-level timestamps
- **DaVinci Resolve compatible**: UTF-8, comma timestamps, no HTML tags, sequential numbering
- **Accepts any format**: WAV, MP3, MP4, MKV, AVI, MOV, WEBM, FLAC, M4A, OGG
- **Futuristic dark UI**: Glassmorphism design with neon accents

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- ffmpeg

## Quick Start

```bash
# Install ffmpeg (if not already installed)
brew install ffmpeg

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the app
.venv/bin/python -m app.main
```

The app opens at `http://localhost:8000`.

## Usage

1. **Drop** an audio or video file onto the upload zone
2. **Select** the language (English, Hindi, or Hinglish)
3. **Click** "Generate Subtitles"
4. **Preview** with karaoke-style word highlighting and audio playback
5. **Download** the `.srt` file and import into DaVinci Resolve

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Speech Engine | mlx-whisper (whisper-large-v3-turbo) |
| Backend | FastAPI + uvicorn |
| Frontend | Vanilla HTML/CSS/JS |
| Audio Extraction | ffmpeg |
| SRT Formatting | srt (Python library) |

## First Run

On first use, the Whisper model (~3GB) will be downloaded automatically. Subsequent runs use the cached model.

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app and routes
│   ├── config.py             # Configuration
│   ├── transcriber.py        # mlx-whisper transcription
│   ├── audio_extractor.py    # ffmpeg audio extraction
│   ├── srt_formatter.py      # Word-level SRT generation
│   ├── job_manager.py        # Background job tracking
│   └── models.py             # Data models
├── static/
│   ├── index.html            # Futuristic dark UI
│   ├── style.css             # Glassmorphism styling
│   └── app.js                # Karaoke engine + upload logic
├── tests/                    # Test suite (50 tests)
└── output/                   # Generated .srt files
```
