import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.types import Message

from .. import db, transcriber

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(msg: Message) -> None:
    db.save_message(
        message_id=msg.message_id,
        user_id=msg.from_user.id if msg.from_user else None,
        username=msg.from_user.username if msg.from_user else None,
        full_name=msg.from_user.full_name if msg.from_user else None,
        text=msg.text or "",
        timestamp=msg.date,
        is_voice=False,
    )
    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[SAVE TEXT] user={name!r}")


@router.message(F.voice)
async def on_voice(msg: Message, bot: Bot) -> None:
    if not msg.voice:
        return
    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[VOICE] from {name!r}")

    try:
        file = await bot.get_file(msg.voice.file_id)
        buf = await bot.download_file(file.file_path)
        audio_bytes = buf.read()
    except Exception:
        logger.exception("Failed to download voice message")
        return

    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, transcriber.transcribe_audio, audio_bytes, ".ogg")
    logger.info(f"[VOICE] transcribed: {text!r}")

    db.save_message(
        message_id=msg.message_id,
        user_id=msg.from_user.id if msg.from_user else None,
        username=msg.from_user.username if msg.from_user else None,
        full_name=msg.from_user.full_name if msg.from_user else None,
        text=text,
        timestamp=msg.date,
        is_voice=True,
    )