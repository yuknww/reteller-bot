import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def transcribe_audio(audio_bytes: bytes, ext: str = ".ogg") -> str:
    """Транскрибирует аудио через Groq Whisper API."""
    try:
        from groq import Groq
    except ImportError:
        logger.error("groq package not installed")
        return "[ошибка: groq не установлен]"

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not set")
        return "[ошибка: GROQ_API_KEY не задан]"

    client = Groq(api_key=api_key)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(f"audio{ext}", f),
                model="whisper-large-v3-turbo",
                language="ru",
                response_format="text",
            )
        text = result.strip() if isinstance(result, str) else str(result).strip()
        return text or "[неразборчиво]"
    except Exception:
        logger.exception("Groq Whisper transcription failed")
        return "[ошибка транскрипции]"
    finally:
        os.unlink(tmp_path)


def get_model():
    """Заглушка — модель не нужна, используем API."""
    logger.info("Using Groq Whisper API for transcription (no local model)")