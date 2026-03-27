import re
from datetime import timedelta

import srt


WORDS_PER_SUBTITLE = 4  # 3-5 words per subtitle chunk


def _clean_text(text: str) -> str:
    """Strip HTML tags and extra whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def words_to_segments(words: list[dict], words_per_sub: int = WORDS_PER_SUBTITLE) -> list[dict]:
    """Group word-level timestamps into short subtitle segments.

    Each word dict has: {'word': str, 'start': float, 'end': float}
    Returns list of: {'start': float, 'end': float, 'text': str}
    """
    if not words:
        return []

    segments = []
    chunk: list[dict] = []

    for word in words:
        cleaned = _clean_text(word.get("word", ""))
        if not cleaned:
            continue

        chunk.append({**word, "word": cleaned})

        if len(chunk) >= words_per_sub:
            segments.append(_chunk_to_segment(chunk))
            chunk = []

    # Remaining words
    if chunk:
        segments.append(_chunk_to_segment(chunk))

    return segments


def _chunk_to_segment(chunk: list[dict]) -> dict:
    """Convert a chunk of words into a single segment."""
    text = " ".join(w["word"] for w in chunk)
    start = chunk[0]["start"]
    end = chunk[-1]["end"]
    # Ensure end > start (guard against bad timestamps)
    if end <= start:
        end = start + 0.1
    return {
        "start": start,
        "end": end,
        "text": text,
    }


def segments_to_srt(words_or_segments: list[dict]) -> str:
    """Convert word-level data or segments to SRT string.

    Accepts either:
    - Word dicts: {'word': str, 'start': float, 'end': float} -> auto-groups into chunks
    - Segment dicts: {'text': str, 'start': float, 'end': float} -> uses as-is
    """
    # Detect format: words have 'word' key, segments have 'text' key
    if not words_or_segments:
        return ""

    first = words_or_segments[0]
    if "word" in first:
        segments = words_to_segments(words_or_segments)
    else:
        segments = words_or_segments

    subtitles = []
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        subtitles.append(
            srt.Subtitle(
                index=i + 1,
                start=timedelta(seconds=seg["start"]),
                end=timedelta(seconds=seg["end"]),
                content=_clean_text(text),
            )
        )

    # Re-index after filtering
    for idx, sub in enumerate(subtitles):
        sub.index = idx + 1

    return srt.compose(subtitles)


def write_srt(content: str, output_path: str) -> None:
    """Write SRT content to file with UTF-8 encoding (DaVinci Resolve compatible)."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
