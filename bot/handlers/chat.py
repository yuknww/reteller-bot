import asyncio
import logging
import re

from aiogram import Router
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import BaseFilter
from aiogram.types import Message

from .. import summarizer
from ..db import get_last_n_messages

router = Router()
logger = logging.getLogger(__name__)

# Устанавливается при старте из main.py
BOT_USERNAME: str = ""


class BotMentionedFilter(BaseFilter):
    """True если бот упомянут в сообщении."""
    async def __call__(self, msg: Message) -> bool:
        if not msg.text or not BOT_USERNAME:
            return False
        if not msg.entities:
            return False
        for entity in msg.entities:
            if entity.type == MessageEntityType.MENTION:
                mention = msg.text[entity.offset : entity.offset + entity.length]
                if mention.lstrip("@").lower() == BOT_USERNAME.lower():
                    return True
        return False


class PrivateChatFilter(BaseFilter):
    """True если сообщение пришло в личку."""
    async def __call__(self, msg: Message) -> bool:
        return msg.chat.type == ChatType.PRIVATE


DEFAULT_CONTEXT_COUNT = 150
_CONTEXT_RE = re.compile(r"\+контекст(?:\s+(\d+))?", re.IGNORECASE)


def _extract_question(text: str) -> tuple[str, int]:
    """Убирает @упоминание бота и +контекст N из текста.
    Возвращает (очищенный вопрос, количество сообщений контекста).
    """
    n = DEFAULT_CONTEXT_COUNT
    m = _CONTEXT_RE.search(text)
    if m:
        if m.group(1):
            n = int(m.group(1))
        text = _CONTEXT_RE.sub("", text)

    if BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\s*", "", text, flags=re.IGNORECASE)

    return text.strip(), n


async def _answer(msg: Message, question: str, context_count: int) -> None:
    if not question:
        question = "Что скажешь об этом?"

    wait = await msg.reply("🤔 Думаю...")
    loop = asyncio.get_running_loop()

    messages = await loop.run_in_executor(None, get_last_n_messages, context_count)
    answer = await loop.run_in_executor(None, summarizer.ask_with_context, question, messages)

    if len(answer) > 300:
        reply_text = f"<blockquote expandable>{answer}</blockquote>"
    else:
        reply_text = answer

    await wait.edit_text(reply_text, parse_mode="HTML")


@router.message(BotMentionedFilter())
async def on_mention(msg: Message) -> None:
    """Ответ на упоминание бота в группе."""
    question, context_count = _extract_question(msg.text or "")

    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[CHAT] mention from {name!r}, context_count={context_count}")
    await _answer(msg, question, context_count)


@router.message(PrivateChatFilter())
async def on_private(msg: Message) -> None:
    """Ответ на любое сообщение в личке (кроме команд — они обработаны раньше)."""
    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[CHAT] private from {name!r}")
    await _answer(msg, msg.text or "", DEFAULT_CONTEXT_COUNT)