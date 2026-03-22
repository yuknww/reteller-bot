from aiogram import Router

from .help import router as help_router
from .retell import router as retell_router
from .tldr import router as tldr_router
from .translate import router as translate_router
from .chat import router as chat_router
from .messages import router as messages_router

router = Router()
router.include_router(help_router)
router.include_router(retell_router)
router.include_router(tldr_router)
router.include_router(translate_router)
router.include_router(chat_router)    # mention + private — перед catch-all
router.include_router(messages_router)  # catch-all — последний
