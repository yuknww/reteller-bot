from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "<b>Команды бота:</b>\n\n"
    "<b>Пересказ чата:</b>\n"
    "/retell day — за сутки\n"
    "/retell week — за неделю\n"
    "/retell 2 — за 2 часа\n"
    "/retell @username — что писал человек за сутки\n"
    "/retell 2@username — что писал человек за 2 часа\n\n"
    "<b>Голосовые:</b>\n"
    "/tldr — краткий пересказ (ответь на голосовое или текст)\n\n"
    "<b>Перевод:</b>\n"
    "/trans es — перевести сообщение (ответь на него)\n"
    "/trans es текст — перевести написанный текст\n"
    "Языки: en, es, ru, de, fr, it, pt, zh…\n\n"
    "<b>ИИ-помощник:</b>\n"
    "Упомяни бота: @retellerpayaso_bot вопрос\n"
    "Или напиши в личку — отвечу без @\n\n"
    "Голосовые транскрибируются и сохраняются автоматически."
)


@router.message(Command("help", "start"))
async def on_help(msg: Message) -> None:
    await msg.reply(HELP_TEXT, parse_mode="HTML")
