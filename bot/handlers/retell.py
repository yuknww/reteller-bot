import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import db, summarizer

router = Router()
logger = logging.getLogger(__name__)

USAGE = (
    "Использование:\n"
    "/retell day — за сутки\n"
    "/retell week — за неделю\n"
    "/retell 2 — за 2 часа\n"
    "/retell @username — что писал человек за сутки\n"
    "/retell 2@username — что писал человек за 2 часа"
)


def _parse_args(arg: str) -> tuple[int, str | None] | None:
    """Разбирает аргумент /retell. Возвращает (hours, username | None) или None при ошибке."""
    username_match = re.search(r"@(\S+)", arg)
    username = username_match.group(1).lower() if username_match else None
    time_part = re.sub(r"@\S+", "", arg).strip().lower()

    if not time_part:
        hours = 24  # по умолчанию — сутки
    elif time_part == "day":
        hours = 24
    elif time_part == "week":
        hours = 24 * 7
    else:
        try:
            hours = max(1, min(int(time_part), 168))
        except ValueError:
            return None

    return hours, username


@router.message(Command("retell"))
async def on_retell(msg: Message) -> None:
    logger.info(f"[CMD /retell] chat_id={msg.chat.id} text={msg.text!r}")

    raw_args = (msg.text or "").split(maxsplit=1)
    arg = raw_args[1].strip() if len(raw_args) > 1 else ""

    parsed = _parse_args(arg)
    if parsed is None:
        await msg.reply(USAGE)
        return

    hours, username = parsed
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    label_time = "за сутки" if hours == 24 else ("за неделю" if hours == 168 else f"за {hours} ч.")

    messages = db.get_messages_since(since)
    loop = asyncio.get_running_loop()

    if username:
        user_messages = [
            m for m in messages
            if (m.get("username") or "").lower() == username
            or username in (m.get("full_name") or "").lower()
        ]
        label = f"сообщения @{username} {label_time}"
        wait = await msg.reply(f"⏳ Собираю {label}...")
        summary = await loop.run_in_executor(
            None, summarizer.summarize_for_user, user_messages, f"@{username}"
        )
        await wait.edit_text(f"👤 <b>{label.capitalize()}:</b>\n\n{summary}", parse_mode="HTML")
    else:
        logger.info(f"[CMD /retell] found {len(messages)} messages")
        wait = await msg.reply(f"⏳ Собираю пересказ {label_time}...")
        summary = await loop.run_in_executor(None, summarizer.summarize, messages)
        await wait.edit_text(f"📋 <b>Пересказ {label_time}:</b>\n\n{summary}", parse_mode="HTML")