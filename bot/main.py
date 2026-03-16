import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from . import db, summarizer, transcriber

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ── /retell — пересказ чата ──────────────────────────────────────────────────
#
# /retell 1         — за 1 час
# /retell day       — за сутки
# /retell week      — за неделю
# /retell @username — сообщения конкретного пользователя за сутки

@dp.message(Command("how"))
async def send_how(message: Message):
    await message.reply("Использование:\n"
                    "/retell 1 — за 1 час\n"
                    "/retell day — за сутки\n"
                    "/retell week — за неделю\n"
                    "/retell @username — что писал человек за сутки\n"
                    "/tldr (в ответ на гс) - пересказ голосового")

@dp.message(Command("retell"))
async def on_retell(msg: Message) -> None:
    logger.info(f"[CMD /retell] chat_id={msg.chat.id} text={msg.text!r}")

    args = (msg.text or "").split(maxsplit=1)
    arg = args[1].strip() if len(args) > 1 else ""

    # /retell @username
    if arg.startswith("@"):
        username = arg.lstrip("@").lower()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        all_messages = db.get_messages_since(since)
        user_messages = [
            m for m in all_messages
            if (m.get("username") or "").lower() == username
            or username in (m.get("full_name") or "").lower()
        ]
        label = f"сообщения @{username} за сутки"
        wait = await msg.reply(f"⏳ Собираю {label}...")
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None, summarizer.summarize_for_user, user_messages, arg
        )
        await wait.edit_text(f"👤 *{label}:*\n\n{summary}", parse_mode="Markdown")
        return

    arg = arg.lower()
    if arg == "day":
        hours = 24
        label = "за сутки"
    elif arg == "week":
        hours = 24 * 7
        label = "за неделю"
    else:
        try:
            hours = max(1, min(int(arg), 168))
            label = f"за {hours} ч."
        except ValueError:
            await msg.reply(
                "Использование:\n"
                "/retell 1 — за 1 час\n"
                "/retell day — за сутки\n"
                "/retell week — за неделю\n"
                "/retell @username — что писал человек за сутки"
            )
            return

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    messages = db.get_messages_since(since)
    logger.info(f"[CMD /retell] found {len(messages)} messages")

    wait = await msg.reply(f"⏳ Собираю пересказ {label}...")
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(None, summarizer.summarize, messages)
    await wait.edit_text(f"📋 *Пересказ {label}:*\n\n{summary}", parse_mode="Markdown")


# ── /tl;dr — краткий пересказ голосового ────────────────────────────────────

@dp.message(Command("tldr"))
async def on_tldr(msg: Message) -> None:
    # Команда должна быть ответом на голосовое сообщение
    replied = msg.reply_to_message
    if not replied:
        await msg.reply("Ответь этой командой на голосовое сообщение.")
        return

    # Если отвечаем на голосовое — транскрибируем и пересказываем
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

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, transcriber.transcribe_audio, audio_bytes, ".ogg")
        author = replied.from_user.full_name if replied.from_user else "Кто-то"
        summary = await loop.run_in_executor(None, summarizer.summarize_voice, text, author)
        await wait.edit_text(f"🎤 _{summary}_", parse_mode="Markdown")
        return

    # Если отвечаем на текст — просто пересказываем текст
    if replied.text:
        author = replied.from_user.full_name if replied.from_user else "Кто-то"
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None, summarizer.summarize_voice, replied.text, author
        )
        await msg.reply(f"💬 _{summary}_", parse_mode="Markdown")
        return

    await msg.reply("Ответь на голосовое или текстовое сообщение.")


# ── Сохранение текстовых сообщений ──────────────────────────────────────────

@dp.message(F.text & ~F.text.startswith("/"))
async def on_text(msg: Message) -> None:
    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[SAVE TEXT] user={name!r} text={msg.text!r}")
    db.save_message(
        message_id=msg.message_id,
        user_id=msg.from_user.id if msg.from_user else None,
        username=msg.from_user.username if msg.from_user else None,
        full_name=msg.from_user.full_name if msg.from_user else None,
        text=msg.text or "",
        timestamp=msg.date,
        is_voice=False,
    )
    logger.info(f"[SAVE TEXT] saved ok")


# ── Голосовые сообщения ──────────────────────────────────────────────────────

@dp.message(F.voice)
async def on_voice(msg: Message) -> None:
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

    loop = asyncio.get_event_loop()
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
    logger.info(f"[VOICE] saved ok")


# ── Ежедневный пересказ + цитата дня в 7:00 ─────────────────────────────────

async def daily_summary() -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    messages = db.get_messages_since(since)
    logger.info(f"[DAILY] running, {len(messages)} messages found")

    loop = asyncio.get_event_loop()

    # Пересказ и цитата параллельно
    summary, quote = await asyncio.gather(
        loop.run_in_executor(None, summarizer.summarize, messages),
        loop.run_in_executor(None, summarizer.pick_quote_of_day, messages),
    )

    text = f"🌅 *Доброе утро! Вот что было в чате за вчера:*\n\n{summary}"
    if quote and "недоступны" not in quote:
        text += f"\n\n💬 *Цитата дня:*\n_{quote}_"

    await bot.send_message(CHAT_ID, text, parse_mode="Markdown")


# ── Запуск ───────────────────────────────────────────────────────────────────

async def main() -> None:
    db.init_db()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, transcriber.get_model)

    tz = os.getenv("SCHEDULER_TZ", "Europe/Moscow")
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(daily_summary, "cron", hour=7, minute=0)
    scheduler.start()

    logger.info(f"Bot started, CHAT_ID={CHAT_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())