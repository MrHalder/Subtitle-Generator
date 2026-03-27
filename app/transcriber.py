import logging
from typing import Callable

import mlx_whisper

from app.config import config

logger = logging.getLogger(__name__)

_model_loaded = False


HINGLISH_PROMPT = (
    "Yeh ek Hinglish conversation hai jisme Hindi aur English dono "
    "languages mix hoti hain. Speaker kabhi Hindi mein baat karta hai "
    "aur kabhi English mein switch karta hai."
)


def load_model() -> None:
    """Pre-load the whisper model into memory. Call at startup."""
    global _model_loaded
    if _model_loaded:
        return
    logger.info("Loading whisper model: %s", config.model_name)
    # Trigger model download and loading by running a tiny transcription
    mlx_whisper.transcribe(
        audio="",  # empty triggers model load without transcription
        path_or_hf_repo=config.model_name,
    )
    _model_loaded = True
    logger.info("Model loaded successfully")


def transcribe(
    audio_path: str,
    language: str,
    on_progress: Callable[[int, str], None] | None = None,
) -> list[dict]:
    """Transcribe audio file and return list of segment dicts.

    Each segment has: {'start': float, 'end': float, 'text': str}

    Args:
        audio_path: Path to audio file (WAV preferred).
        language: Language code ('en', 'hi', 'hi-en' for Hinglish).
        on_progress: Callback(progress_percent, stage_text).

    Returns:
        List of segment dictionaries.
    """
    whisper_lang = "hi" if language in ("hi", "hi-en") else language
    initial_prompt = HINGLISH_PROMPT if language == "hi-en" else None

    if on_progress:
        on_progress(0, "Starting transcription...")

    result = mlx_whisper.transcribe(
        audio=audio_path,
        path_or_hf_repo=config.model_name,
        language=whisper_lang,
        initial_prompt=initial_prompt,
        word_timestamps=True,
        verbose=False,
    )

    raw_segments = result.get("segments", [])

    # Extract word-level timestamps for short subtitle chunks
    words = []
    total_duration = raw_segments[-1]["end"] if raw_segments else 1.0

    for seg in raw_segments:
        seg_words = seg.get("words", [])
        for w in seg_words:
            word_text = w.get("word", "").strip()
            if word_text:
                words.append({
                    "word": word_text,
                    "start": w["start"],
                    "end": w["end"],
                })

        if on_progress:
            progress = int((seg["end"] / total_duration) * 100)
            on_progress(min(progress, 99), "Transcribing...")

    if on_progress:
        on_progress(99, "Transcription complete")

    return words
