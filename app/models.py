from dataclasses import dataclass


@dataclass(frozen=True)
class JobState:
    job_id: str
    status: str  # "queued" | "extracting" | "transcribing" | "formatting" | "complete" | "error"
    progress: int  # 0-100
    stage: str  # human-readable stage description
    error: str | None = None
    srt_path: str | None = None
    words_path: str | None = None  # JSON file with word-level timestamps
    audio_path: str | None = None  # extracted audio for playback
    original_filename: str = ""
