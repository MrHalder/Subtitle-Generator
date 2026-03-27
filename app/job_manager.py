import threading
from dataclasses import replace

from app.models import JobState


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create_job(self, job_id: str, filename: str) -> JobState:
        state = JobState(
            job_id=job_id,
            status="queued",
            progress=0,
            stage="Queued",
            original_filename=filename,
        )
        with self._lock:
            self._jobs[job_id] = state
        return state

    def update_progress(self, job_id: str, progress: int, stage: str, status: str = "transcribing") -> JobState:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                raise KeyError(f"Job {job_id} not found")
            updated = replace(current, progress=min(progress, 99), stage=stage, status=status)
            self._jobs[job_id] = updated
        return updated

    def complete_job(
        self,
        job_id: str,
        srt_path: str,
        words_path: str | None = None,
        audio_path: str | None = None,
    ) -> JobState:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                raise KeyError(f"Job {job_id} not found")
            updated = replace(
                current,
                status="complete",
                progress=100,
                stage="Complete",
                srt_path=srt_path,
                words_path=words_path,
                audio_path=audio_path,
            )
            self._jobs[job_id] = updated
        return updated

    def fail_job(self, job_id: str, error: str) -> JobState:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                raise KeyError(f"Job {job_id} not found")
            updated = replace(current, status="error", stage="Error", error=error)
            self._jobs[job_id] = updated
        return updated

    def get_job(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)


job_manager = JobManager()
