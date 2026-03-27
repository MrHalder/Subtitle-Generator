from dataclasses import dataclass
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class Config:
    model_name: str = "mlx-community/whisper-large-v3-turbo"  # English
    hinglish_model_name: str = "Oriserve/Whisper-Hindi2Hinglish-Apex"  # Hindi + Hinglish
    temp_dir: Path = Path(tempfile.gettempdir()) / "subtitle_generator"
    output_dir: Path = Path(__file__).parent.parent / "output"
    max_file_size_bytes: int = 2 * 1024 * 1024 * 1024  # 2GB

    audio_extensions: tuple[str, ...] = (
        ".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma",
    )
    video_extensions: tuple[str, ...] = (
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    )

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.audio_extensions + self.video_extensions

    languages: dict[str, str] = None  # set in __post_init__

    def __post_init__(self) -> None:
        object.__setattr__(self, "languages", {
            "en": "English",
            "hi": "Hindi",
            "hi-en": "Hinglish",
        })
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


config = Config()
