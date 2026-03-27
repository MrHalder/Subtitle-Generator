from app.srt_formatter import segments_to_srt, words_to_segments, _clean_text, write_srt
import tempfile
from pathlib import Path


class TestCleanText:
    def test_strips_html_tags(self):
        assert _clean_text("<b>Hello</b> <i>world</i>") == "Hello world"

    def test_strips_whitespace(self):
        assert _clean_text("  Hello world  ") == "Hello world"

    def test_empty_string(self):
        assert _clean_text("") == ""


class TestWordsToSegments:
    def test_groups_words_into_chunks(self):
        words = [
            {"word": "din", "start": 0.0, "end": 0.3},
            {"word": "ka", "start": 0.3, "end": 0.5},
            {"word": "1", "start": 0.5, "end": 0.7},
            {"word": "million", "start": 0.7, "end": 1.0},
            {"word": "aur", "start": 1.0, "end": 1.2},
            {"word": "100", "start": 1.2, "end": 1.5},
            {"word": "din", "start": 1.5, "end": 1.7},
            {"word": "mein", "start": 1.7, "end": 2.0},
        ]
        segments = words_to_segments(words, words_per_sub=4)
        assert len(segments) == 2
        assert segments[0]["text"] == "din ka 1 million"
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 1.0
        assert segments[1]["text"] == "aur 100 din mein"
        assert segments[1]["start"] == 1.0
        assert segments[1]["end"] == 2.0

    def test_handles_remainder(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
            {"word": "foo", "start": 1.0, "end": 1.5},
        ]
        segments = words_to_segments(words, words_per_sub=4)
        assert len(segments) == 1
        assert segments[0]["text"] == "hello world foo"

    def test_empty_words(self):
        assert words_to_segments([]) == []

    def test_skips_empty_words(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "  ", "start": 0.5, "end": 0.6},
            {"word": "world", "start": 0.6, "end": 1.0},
        ]
        segments = words_to_segments(words, words_per_sub=4)
        assert len(segments) == 1
        assert segments[0]["text"] == "hello world"

    def test_custom_words_per_sub(self):
        words = [
            {"word": f"w{i}", "start": float(i), "end": float(i + 1)}
            for i in range(10)
        ]
        segments = words_to_segments(words, words_per_sub=3)
        assert len(segments) == 4  # 3+3+3+1
        assert segments[0]["text"] == "w0 w1 w2"
        assert segments[3]["text"] == "w9"

    def test_hindi_words(self):
        words = [
            {"word": "नमस्ते", "start": 0.0, "end": 0.5},
            {"word": "दुनिया", "start": 0.5, "end": 1.0},
        ]
        segments = words_to_segments(words, words_per_sub=4)
        assert len(segments) == 1
        assert "नमस्ते" in segments[0]["text"]


class TestSegmentsToSrt:
    def test_word_format_input(self):
        words = [
            {"word": "din", "start": 0.0, "end": 0.3},
            {"word": "ka", "start": 0.3, "end": 0.5},
            {"word": "1", "start": 0.5, "end": 0.7},
            {"word": "million", "start": 0.7, "end": 1.0},
            {"word": "aur", "start": 1.0, "end": 1.2},
        ]
        result = segments_to_srt(words)
        assert "din ka 1 million" in result
        assert "aur" in result
        assert "00:00:00,000" in result

    def test_segment_format_input(self):
        segments = [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 2.5, "end": 5.0, "text": "How are you"},
        ]
        result = segments_to_srt(segments)
        assert "Hello world" in result
        assert "How are you" in result

    def test_uses_comma_not_period_in_timestamps(self):
        words = [{"word": "test", "start": 1.234, "end": 5.678}]
        result = segments_to_srt(words)
        lines = result.strip().split("\n")
        timestamp_line = lines[1]
        assert "," in timestamp_line
        assert "." not in timestamp_line

    def test_empty_input(self):
        result = segments_to_srt([])
        assert result == ""

    def test_sequential_numbering(self):
        words = [
            {"word": f"w{i}", "start": float(i), "end": float(i) + 0.5}
            for i in range(8)
        ]
        result = segments_to_srt(words)
        assert "1\n" in result
        assert "2\n" in result

    def test_large_timestamp(self):
        words = [{"word": "late", "start": 3661.5, "end": 3665.0}]
        result = segments_to_srt(words)
        assert "01:01:01,500" in result


class TestWriteSrt:
    def test_writes_utf8_file(self):
        content = "1\n00:00:00,000 --> 00:00:01,000\nनमस्ते\n\n"
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            path = f.name

        write_srt(content, path)
        result = Path(path).read_text(encoding="utf-8")
        assert "नमस्ते" in result
        Path(path).unlink()
