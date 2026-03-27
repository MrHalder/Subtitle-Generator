import subprocess
from pathlib import Path

from app.config import config


def is_video_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in config.video_extensions


def is_supported_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in config.supported_extensions


def extract_audio(input_path: str, output_path: str) -> str:
    """Extract audio from video file to 16kHz mono WAV for Whisper.

    If input is already an audio file, converts to WAV format.
    Returns the path to the extracted/converted audio file.

    Raises:
        RuntimeError: If ffmpeg fails to extract/convert audio.
    """
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vn",                 # no video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",        # 16kHz sample rate
        "-ac", "1",            # mono
        "-y",                  # overwrite output
        output_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 min timeout
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip().split("\n")[-1] if result.stderr else "Unknown ffmpeg error"
        raise RuntimeError(f"Audio extraction failed: {error_msg}")

    if not Path(output_path).exists():
        raise RuntimeError("Audio extraction produced no output file")

    return output_path
