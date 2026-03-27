import pytest
from app.job_manager import JobManager


@pytest.fixture
def manager():
    return JobManager()


class TestJobManager:
    def test_create_job(self, manager):
        job = manager.create_job("test-1", "video.mp4")
        assert job.job_id == "test-1"
        assert job.status == "queued"
        assert job.progress == 0
        assert job.original_filename == "video.mp4"
        assert job.error is None
        assert job.srt_path is None

    def test_get_job(self, manager):
        manager.create_job("test-1", "video.mp4")
        job = manager.get_job("test-1")
        assert job is not None
        assert job.job_id == "test-1"

    def test_get_nonexistent_job(self, manager):
        assert manager.get_job("nonexistent") is None

    def test_update_progress(self, manager):
        manager.create_job("test-1", "video.mp4")
        updated = manager.update_progress("test-1", 50, "Transcribing...")
        assert updated.progress == 50
        assert updated.stage == "Transcribing..."
        assert updated.status == "transcribing"

    def test_progress_capped_at_99(self, manager):
        manager.create_job("test-1", "video.mp4")
        updated = manager.update_progress("test-1", 150, "Overflow")
        assert updated.progress == 99

    def test_complete_job(self, manager):
        manager.create_job("test-1", "video.mp4")
        completed = manager.complete_job("test-1", "/output/test.srt")
        assert completed.status == "complete"
        assert completed.progress == 100
        assert completed.srt_path == "/output/test.srt"

    def test_fail_job(self, manager):
        manager.create_job("test-1", "video.mp4")
        failed = manager.fail_job("test-1", "Something broke")
        assert failed.status == "error"
        assert failed.error == "Something broke"

    def test_update_nonexistent_raises(self, manager):
        with pytest.raises(KeyError):
            manager.update_progress("nope", 50, "test")

    def test_complete_nonexistent_raises(self, manager):
        with pytest.raises(KeyError):
            manager.complete_job("nope", "/path")

    def test_fail_nonexistent_raises(self, manager):
        with pytest.raises(KeyError):
            manager.fail_job("nope", "error")

    def test_immutability_original_unchanged(self, manager):
        original = manager.create_job("test-1", "video.mp4")
        manager.update_progress("test-1", 50, "Working")
        # Original reference should still show old values
        assert original.progress == 0
        assert original.status == "queued"

    def test_job_state_is_frozen(self, manager):
        job = manager.create_job("test-1", "video.mp4")
        with pytest.raises(AttributeError):
            job.status = "complete"
