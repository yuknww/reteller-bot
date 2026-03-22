import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from . import db, summarizer, transcriber
from .handlers import router
from .handlers import chat as chat_handler

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

BOT_COMMANDS = [
    BotCommand(command="retell", description="Пересказ чата (day / week / 2 / @user / 2@user)"),
    BotCommand(command="tldr", description="Краткий пересказ голосового или текста"),
    BotCommand(command="trans", description="Перевод (es / en / ru…) — ответь на сообщение"),
    BotCommand(command="help", description="Справка"),
]


# ── Ежедневный пересказ + цитата дня в 7:00 ─────────────────────────────────

async def daily_summary() -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    messages = db.get_messages_since(since)
    logger.info(f"[DAILY] running, {len(messages)} messages found")

    loop = asyncio.get_running_loop()
    summary, quote = await asyncio.gather(
        loop.run_in_executor(None, summarizer.summarize, messages),
        loop.run_in_executor(None, summarizer.pick_quote_of_day, messages),
    )

    text = f"🌅 <b>Доброе утро! Вот что было в чате за вчера:</b>\n\n{summary}"
    if quote and "недоступны" not in quote:
        text += f"\n\n💬 <b>Цитата дня:</b>\n{quote}"

    await bot.send_message(CHAT_ID, text, parse_mode="HTML")


# ── Запуск ───────────────────────────────────────────────────────────────────

async def main() -> None:
    db.init_db()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, transcriber.get_model)

    await bot.set_my_commands(BOT_COMMANDS)

    me = await bot.get_me()
    chat_handler.BOT_USERNAME = me.username or ""
    logger.info(f"Bot username: @{chat_handler.BOT_USERNAME}")

    tz = os.getenv("SCHEDULER_TZ", "Europe/Moscow")
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(daily_summary, "cron", hour=7, minute=0)
    scheduler.start()

    dp.include_router(router)

    logger.info(f"Bot started, CHAT_ID={CHAT_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())