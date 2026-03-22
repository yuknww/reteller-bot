import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import summarizer, transcriber

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("tldr"))
async def on_tldr(msg: Message, bot: Bot) -> None:
    replied = msg.reply_to_message
    if not replied:
        await msg.reply("Ответь этой командой на голосовое или текстовое сообщение.")
        return

    loop = asyncio.get_running_loop()
    author = replied.from_user.full_name if replied.from_user else "Кто-то"

    if replied.voice:
        wait = await msg.reply("⏳ Слушаю...")
        try:
            file = await bot.get_file(replied.voice.file_id)
            buf = await bot.download_file(file.file_path)
            audio_bytes = buf.read()
        except Exception:
            logger.exception("Failed to download voice for tldr")
            await wait.edit_text("Не удалось скачать голосовое.")
            return

        text = await loop.run_in_executor(None, transcriber.transcribe_audio, audio_bytes, ".ogg")
        summary = await loop.run_in_executor(None, summarizer.summarize_voice, text, author)
        await wait.edit_text(
            f"🎤 <b>{author}</b>\n<blockquote expandable>{summary}</blockquote>",
            parse_mode="HTML",
        )
        return

    if replied.text:
        summary = await loop.run_in_executor(None, summarizer.summarize_voice, replied.text, author)
        await msg.reply(
            f"💬 <b>{author}</b>\n<blockquote>{summary}</blockquote>",
            parse_mode="HTML",
        )
        return

    await msg.reply("Ответь на голосовое или текстовое сообщение.")