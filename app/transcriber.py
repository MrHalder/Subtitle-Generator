import logging
import re
import subprocess
import tempfile
import wave
from typing import Callable

import numpy as np
import mlx_whisper

from app.config import config

logger = logging.getLogger(__name__)

_hinglish_model = None
_hinglish_processor = None

# Hindi number words -> digits
HINDI_NUMBERS = {
    "ek": "1", "do": "2", "teen": "3", "chaar": "4", "paanch": "5",
    "chheh": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
    "gyarah": "11", "barah": "12", "terah": "13", "chaudah": "14",
    "pandrah": "15", "solah": "16", "satrah": "17", "aathrah": "18",
    "unees": "19", "bees": "20", "pachees": "25", "tees": "30",
    "chalees": "40", "pachaas": "50", "sattar": "70",
    "assi": "80", "nabbe": "90", "sau": "100", "hazaar": "1000",
    "lakh": "lakh", "karod": "crore", "crore": "crore",
    "million": "million", "billion": "billion",
}


def _get_hinglish_model():
    """Lazy-load the Oriserve Hinglish model + processor."""
    global _hinglish_model, _hinglish_processor
    if _hinglish_model is not None:
        return _hinglish_model, _hinglish_processor

    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    logger.info("Loading Hinglish model: %s", config.hinglish_model_name)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.float16 if device == "mps" else torch.float32

    _hinglish_processor = WhisperProcessor.from_pretrained(config.hinglish_model_name)
    _hinglish_model = WhisperForConditionalGeneration.from_pretrained(
        config.hinglish_model_name, torch_dtype=dtype,
    ).to(device)

    logger.info("Hinglish model loaded on %s", device)
    return _hinglish_model, _hinglish_processor


def _load_audio_as_numpy(audio_path: str) -> tuple[np.ndarray, int]:
    """Load any audio file as 16kHz mono float32 numpy array."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        ["ffmpeg", "-i", audio_path, "-ar", "16000", "-ac", "1",
         "-acodec", "pcm_s16le", "-y", tmp_path],
        capture_output=True, timeout=120,
    )

    with wave.open(tmp_path, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        sr = wf.getframerate()

    import os
    os.unlink(tmp_path)
    return audio_np, sr


def _postprocess_word(word: str) -> str:
    """Clean a single word for Hinglish subtitle output."""
    word = word.lower().strip()
    # Strip all trailing punctuation
    word = re.sub(r"[.,!?;:]+$", "", word)
    # Number conversion
    if word in HINDI_NUMBERS:
        return HINDI_NUMBERS[word]
    return word


def _filter_words(words: list[dict]) -> list[dict]:
    """Filter bad timestamps and hallucinated repetitions."""
    filtered = [w for w in words if w["end"] > w["start"] and w["end"] - w["start"] >= 0.01]

    deduped = []
    repeat_count = 0
    for i, w in enumerate(filtered):
        if i > 0 and w["word"].lower().strip() == filtered[i - 1]["word"].lower().strip():
            repeat_count += 1
            if repeat_count >= 3:
                continue
        else:
            repeat_count = 0
        deduped.append(w)

    return deduped


def _transcribe_hinglish(
    audio_path: str,
    on_progress: Callable[[int, str], None] | None = None,
) -> list[dict]:
    """Transcribe using Oriserve Hindi2Hinglish model.

    Uses model.generate() for text, then aligns words using
    mlx-whisper word timestamps as a secondary pass.
    """
    import torch

    if on_progress:
        on_progress(5, "Loading Hinglish model...")

    model, processor = _get_hinglish_model()
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype

    if on_progress:
        on_progress(10, "Loading audio...")

    audio_np, sr = _load_audio_as_numpy(audio_path)
    total_duration = len(audio_np) / sr

    if on_progress:
        on_progress(15, "Transcribing (Hinglish)...")

    # Step 1: Get clean Hinglish text from Oriserve model
    input_features = processor(
        audio_np, sampling_rate=16000, return_tensors="pt"
    ).input_features.to(device, dtype=dtype)

    with torch.no_grad():
        ids = model.generate(input_features, return_timestamps=True)

    raw_text = processor.decode(ids[0], skip_special_tokens=True).strip()
    logger.info("Oriserve raw text: %s", raw_text[:200])

    if on_progress:
        on_progress(50, "Getting word timestamps...")

    # Step 2: Get word-level timestamps from mlx-whisper
    mlx_result = mlx_whisper.transcribe(
        audio=audio_path,
        path_or_hf_repo=config.model_name,
        language="hi",
        word_timestamps=True,
        verbose=False,
        condition_on_previous_text=False,
    )

    # Extract mlx word timings
    mlx_words = []
    for seg in mlx_result.get("segments", []):
        for w in seg.get("words", []):
            text = w.get("word", "").strip()
            if text and w["end"] > w["start"]:
                mlx_words.append({
                    "start": w["start"],
                    "end": w["end"],
                })

    if on_progress:
        on_progress(85, "Aligning words...")

    # Step 3: Align Oriserve text with mlx timestamps
    oriserve_words = raw_text.split()

    if mlx_words and len(mlx_words) >= len(oriserve_words) * 0.5:
        # Use mlx timestamps, distributed across oriserve words
        words = _align_text_with_timestamps(oriserve_words, mlx_words, total_duration)
    else:
        # Fallback: evenly distribute across duration
        words = _distribute_evenly(oriserve_words, 0.0, total_duration)

    # Step 4: Post-process each word
    result = []
    for w in words:
        cleaned = _postprocess_word(w["word"])
        if cleaned:
            result.append({**w, "word": cleaned})

    if on_progress:
        on_progress(99, "Transcription complete")

    return _filter_words(result)


def _align_text_with_timestamps(
    text_words: list[str],
    timestamp_words: list[dict],
    total_duration: float,
) -> list[dict]:
    """Align text words with timestamp data.

    Maps N text words onto M timestamp slots proportionally,
    ensuring monotonically increasing timestamps with no overlaps.
    """
    n_text = len(text_words)
    n_ts = len(timestamp_words)

    if n_text == 0:
        return []

    # Get the full time range from timestamp data
    ts_start = timestamp_words[0]["start"]
    ts_end = timestamp_words[-1]["end"]
    ts_duration = ts_end - ts_start

    if ts_duration <= 0:
        return _distribute_evenly(text_words, ts_start, total_duration)

    # Assign each text word a proportional slice of the timeline
    per_word_dur = ts_duration / n_text
    words = []
    for i, text in enumerate(text_words):
        w_start = ts_start + i * per_word_dur
        w_end = ts_start + (i + 1) * per_word_dur

        # Snap to nearest real timestamp boundary for better accuracy
        ts_idx = min(int(i * n_ts / n_text), n_ts - 1)
        real_start = timestamp_words[ts_idx]["start"]

        # Use real start if it's close to our proportional start
        if abs(real_start - w_start) < per_word_dur * 0.6:
            w_start = real_start

        # Ensure monotonic and no overlap
        if words and w_start < words[-1]["end"]:
            w_start = words[-1]["end"]
        if w_end <= w_start:
            w_end = w_start + 0.15

        words.append({
            "word": text,
            "start": round(w_start, 3),
            "end": round(w_end, 3),
        })

    return words


def _distribute_evenly(words: list[str], start: float, end: float) -> list[dict]:
    """Distribute words evenly across a time range."""
    if not words:
        return []
    duration = end - start
    per_word = duration / len(words)
    return [
        {
            "word": w,
            "start": round(start + i * per_word, 3),
            "end": round(start + (i + 1) * per_word, 3),
        }
        for i, w in enumerate(words)
    ]


def _transcribe_mlx(
    audio_path: str,
    language: str,
    on_progress: Callable[[int, str], None] | None = None,
) -> list[dict]:
    """Transcribe using mlx-whisper (for English)."""
    if on_progress:
        on_progress(5, "Starting transcription...")

    result = mlx_whisper.transcribe(
        audio=audio_path,
        path_or_hf_repo=config.model_name,
        language=language,
        word_timestamps=True,
        verbose=False,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    )

    raw_segments = result.get("segments", [])
    words = []
    total_duration = raw_segments[-1]["end"] if raw_segments else 1.0

    for seg in raw_segments:
        if seg.get("compression_ratio", 0) > 2.4:
            continue
        if seg.get("no_speech_prob", 0) > 0.6:
            continue
        for w in seg.get("words", []):
            word_text = w.get("word", "").strip()
            if word_text:
                words.append({"word": word_text, "start": w["start"], "end": w["end"]})

        if on_progress:
            progress = int((seg["end"] / total_duration) * 100)
            on_progress(min(progress, 95), "Transcribing...")

    if on_progress:
        on_progress(95, "Transcription complete")

    return _filter_words(words)


def transcribe(
    audio_path: str,
    language: str,
    on_progress: Callable[[int, str], None] | None = None,
) -> list[dict]:
    """Transcribe audio file. Routes to best model by language."""
    if language in ("hi", "hi-en"):
        return _transcribe_hinglish(audio_path, on_progress)
    else:
        return _transcribe_mlx(audio_path, language, on_progress)
