import asyncio
import json
import logging
import threading
import uuid
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.audio_extractor import extract_audio, is_video_file, is_supported_file
from app.config import config
from app.job_manager import job_manager
from app.srt_formatter import segments_to_srt, write_srt
from app.transcriber import transcribe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Subtitle Generator", version="1.0.0")

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC_DIR / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/api/languages")
async def get_languages():
    return {"languages": config.languages}


@app.post("/api/upload")
async def upload_file(file: UploadFile, language: str = Form("en")):
    if language not in config.languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in config.supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(config.supported_extensions)}",
        )

    job_id = str(uuid.uuid4())
    temp_path = config.temp_dir / f"{job_id}{ext}"

    with open(temp_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    file_size = temp_path.stat().st_size
    if file_size > config.max_file_size_bytes:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 2GB.")

    job_manager.create_job(job_id, file.filename)

    thread = threading.Thread(
        target=_run_transcription,
        args=(job_id, str(temp_path), language),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            current = job_manager.get_job(job_id)
            if current is None:
                break

            data = {
                "status": current.status,
                "progress": current.progress,
                "stage": current.stage,
                "error": current.error,
            }
            yield f"data: {json.dumps(data)}\n\n"

            if current.status in ("complete", "error"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/preview/{job_id}")
async def preview_srt(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=400, detail="Transcription not complete yet")
    if job.srt_path is None:
        raise HTTPException(status_code=500, detail="SRT file path missing")

    content = Path(job.srt_path).read_text(encoding="utf-8")

    # Load word-level timestamps for karaoke preview
    words_data = []
    if job.words_path and Path(job.words_path).exists():
        words_data = json.loads(Path(job.words_path).read_text(encoding="utf-8"))

    return {
        "srt_content": content,
        "filename": job.original_filename,
        "words": words_data,
        "has_audio": job.audio_path is not None and Path(job.audio_path).exists(),
    }


@app.get("/api/audio/{job_id}")
async def serve_audio(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.audio_path is None or not Path(job.audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio not available")

    return FileResponse(
        path=job.audio_path,
        media_type="audio/wav",
    )


@app.get("/api/download/{job_id}")
async def download_srt(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=400, detail="Transcription not complete yet")
    if job.srt_path is None:
        raise HTTPException(status_code=500, detail="SRT file path missing")

    srt_filename = Path(job.original_filename).stem + ".srt"
    return FileResponse(
        path=job.srt_path,
        filename=srt_filename,
        media_type="application/x-subrip",
    )


def _run_transcription(job_id: str, file_path: str, language: str) -> None:
    """Run the full transcription pipeline in a background thread."""
    audio_path = file_path
    try:
        # Step 1: Extract audio if video (or convert audio to WAV for playback)
        wav_path = str(config.temp_dir / f"{job_id}.wav")
        if is_video_file(file_path):
            job_manager.update_progress(job_id, 0, "Extracting audio...", status="extracting")
            extract_audio(file_path, wav_path)
            audio_path = wav_path
        elif not file_path.lower().endswith(".wav"):
            # Convert non-WAV audio to WAV for browser playback
            job_manager.update_progress(job_id, 0, "Converting audio...", status="extracting")
            extract_audio(file_path, wav_path)
            audio_path = wav_path
        else:
            # Already WAV — use in place (file_path is already in temp dir)
            audio_path = file_path

        # Step 2: Transcribe (returns word-level data)
        job_manager.update_progress(job_id, 5, "Starting transcription...", status="transcribing")

        def on_progress(progress: int, stage: str) -> None:
            job_manager.update_progress(job_id, progress, stage, status="transcribing")

        words = transcribe(audio_path, language, on_progress=on_progress)

        # Step 3: Format SRT from word data
        job_manager.update_progress(job_id, 99, "Formatting subtitles...", status="formatting")
        srt_content = segments_to_srt(words)

        # Step 4: Save SRT
        srt_path = config.output_dir / f"{job_id}.srt"
        write_srt(srt_content, str(srt_path))

        # Step 5: Save word-level timestamps for karaoke preview
        words_path = config.output_dir / f"{job_id}_words.json"
        words_path.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")

        # Keep audio for playback (don't delete wav_path)
        job_manager.complete_job(
            job_id,
            str(srt_path),
            words_path=str(words_path),
            audio_path=audio_path,
        )
        logger.info("Job %s completed successfully", job_id)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job_manager.fail_job(job_id, str(e))

    finally:
        # Only cleanup the original upload, keep wav for playback
        if file_path != audio_path:
            Path(file_path).unlink(missing_ok=True)


def start() -> None:
    """Entry point for the subtitle generator."""
    logger.info("Starting Subtitle Generator at http://localhost:8000")
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start()
