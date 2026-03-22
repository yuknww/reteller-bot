import asyncio
import logging
import re

from aiogram import Router
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import BaseFilter
from aiogram.types import Message

from .. import summarizer

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


def _extract_question(text: str) -> str:
    """Убирает @упоминание бота из текста."""
    if not BOT_USERNAME:
        return text.strip()
    return re.sub(rf"@{re.escape(BOT_USERNAME)}\s*", "", text, flags=re.IGNORECASE).strip()


async def _answer(msg: Message, question: str, context: str = "") -> None:
    if not question and not context:
        await msg.reply("Да? 👂 Спроси что-нибудь.")
        return

    full_prompt = context + (question or "Что скажешь об этом?")
    wait = await msg.reply("🤔 Думаю...")
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, summarizer.ask_assistant, full_prompt)

    if len(answer) > 300:
        reply_text = f"<blockquote expandable>{answer}</blockquote>"
    else:
        reply_text = answer

    await wait.edit_text(reply_text, parse_mode="HTML")


@router.message(BotMentionedFilter())
async def on_mention(msg: Message) -> None:
    """Ответ на упоминание бота в группе."""
    question = _extract_question(msg.text or "")

    context = ""
    if msg.reply_to_message and msg.reply_to_message.text:
        reply_author = (
            msg.reply_to_message.from_user.full_name
            if msg.reply_to_message.from_user
            else "кто-то"
        )
        context = f"Контекст — сообщение от {reply_author}: «{msg.reply_to_message.text}»\n\n"

    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[CHAT] mention from {name!r}")
    await _answer(msg, question, context)


@router.message(PrivateChatFilter())
async def on_private(msg: Message) -> None:
    """Ответ на любое сообщение в личке (кроме команд — они обработаны раньше)."""
    name = msg.from_user.full_name if msg.from_user else "?"
    logger.info(f"[CHAT] private from {name!r}")
    await _answer(msg, msg.text or "")