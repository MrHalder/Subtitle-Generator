from app.audio_extractor import is_video_file, is_supported_file


class TestIsVideoFile:
    def test_mp4_is_video(self):
        assert is_video_file("test.mp4") is True

    def test_mkv_is_video(self):
        assert is_video_file("test.mkv") is True

    def test_avi_is_video(self):
        assert is_video_file("test.avi") is True

    def test_mov_is_video(self):
        assert is_video_file("test.mov") is True

    def test_webm_is_video(self):
        assert is_video_file("test.webm") is True

    def test_wav_is_not_video(self):
        assert is_video_file("test.wav") is False

    def test_mp3_is_not_video(self):
        assert is_video_file("test.mp3") is False

    def test_flac_is_not_video(self):
        assert is_video_file("test.flac") is False

    def test_case_insensitive(self):
        assert is_video_file("test.MP4") is True
        assert is_video_file("test.Mkv") is True

    def test_path_with_directories(self):
        assert is_video_file("/path/to/video.mp4") is True
        assert is_video_file("/path/to/audio.wav") is False


class TestIsSupportedFile:
    def test_audio_files_supported(self):
        assert is_supported_file("test.wav") is True
        assert is_supported_file("test.mp3") is True
        assert is_supported_file("test.flac") is True
        assert is_supported_file("test.m4a") is True
        assert is_supported_file("test.ogg") is True

    def test_video_files_supported(self):
        assert is_supported_file("test.mp4") is True
        assert is_supported_file("test.mkv") is True
        assert is_supported_file("test.avi") is True

    def test_unsupported_files(self):
        assert is_supported_file("test.txt") is False
        assert is_supported_file("test.pdf") is False
        assert is_supported_file("test.jpg") is False
        assert is_supported_file("test.py") is False

    def test_case_insensitive(self):
        assert is_supported_file("test.WAV") is True
        assert is_supported_file("test.Mp3") is True
