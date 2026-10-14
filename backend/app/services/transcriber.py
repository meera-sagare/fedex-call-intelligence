"""Speech-to-text for uploaded call recordings using faster-whisper (optional dependency)."""
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


class TranscriptionUnavailable(RuntimeError):
    """The speech-to-text engine is not installed or cannot run."""


class NoSpeechDetected(ValueError):
    """The recording decoded fine but contained no recognizable speech."""


@lru_cache
def _model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionUnavailable(
            "Audio transcription is not installed. Run `pip install -r requirements-transcription.txt`, "
            "or provide the transcript text with the upload."
        ) from exc
    return WhisperModel(get_settings().whisper_model, device="cpu", compute_type="int8")


def transcribe(audio_path: Path) -> str:
    segments, _info = _model().transcribe(str(audio_path), vad_filter=True)
    text = "\n".join(seg.text.strip() for seg in segments if seg.text.strip())
    if not text:
        raise NoSpeechDetected("No speech was detected in the recording")
    return text
