import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import summarizer, transcriber

router = Router()
logger = logging.getLogger(__name__)

LANG_NAMES: dict[str, str] = {
    "ru": "русский", "en": "английский", "es": "испанский",
    "de": "немецкий", "fr": "французский", "it": "итальянский",
    "pt": "португальский", "zh": "китайский", "ja": "японский",
    "ko": "корейский", "ar": "арабский", "tr": "турецкий",
    "pl": "польский", "uk": "украинский",
}

USAGE = (
    "Использование:\n"
    "/trans es — перевести сообщение (ответь на него)\n"
    "/trans es текст — перевести написанный текст\n"
    "Язык: en, es, ru, de, fr, it, pt… (по умолчанию: ru)"
)


def _lang_display(lang: str) -> str:
    return LANG_NAMES.get(lang.lower(), lang)


@router.message(Command("trans"))
async def on_trans(msg: Message, bot: Bot) -> None:
    parts = (msg.text or "").split(maxsplit=2)
    lang = parts[1] if len(parts) >= 2 else "ru"
    inline_text = parts[2] if len(parts) >= 3 else None

    replied = msg.reply_to_message
    loop = asyncio.get_running_loop()

    # ── источник текста ───────────────────────────────────────────────────────
    if inline_text:
        source_text = inline_text
        source_author = None

    elif replied and replied.text:
        source_text = replied.text
        source_author = replied.from_user.full_name if replied.from_user else None

    elif replied and replied.voice:
        wait = await msg.reply("🎤 Транскрибирую...")
        try:
            file = await bot.get_file(replied.voice.file_id)
            buf = await bot.download_file(file.file_path)
            audio_bytes = buf.read()
        except Exception:
            logger.exception("Failed to download voice for /trans")
            await wait.edit_text("Не удалось скачать голосовое.")
            return

        source_text = await loop.run_in_executor(
            None, transcriber.transcribe_audio, audio_bytes, ".ogg"
        )
        source_author = replied.from_user.full_name if replied.from_user else None

        translation = await loop.run_in_executor(
            None, summarizer.translate_text, source_text, lang
        )
        header = f"🌐 <b>{_lang_display(lang).capitalize()}</b>"
        if source_author:
            header += f" · {source_author}"
        await wait.edit_text(
            f"{header}\n<blockquote expandable>{translation}</blockquote>",
            parse_mode="HTML",
        )
        return

    else:
        await msg.reply(USAGE)
        return

    # ── перевод ───────────────────────────────────────────────────────────────
    wait = await msg.reply(f"🌐 Перевожу на {_lang_display(lang)}...")
    translation = await loop.run_in_executor(
        None, summarizer.translate_text, source_text, lang
    )
    header = f"🌐 <b>{_lang_display(lang).capitalize()}</b>"
    if source_author:
        header += f" · {source_author}"
    await wait.edit_text(
        f"{header}\n<blockquote expandable>{translation}</blockquote>",
        parse_mode="HTML",
    )
