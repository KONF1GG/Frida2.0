"""
Обработчик команды /start.
Приветствует пользователя и регистрирует его в системе.
"""

import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.utils.decorators import check_and_add_user, send_typing_action

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
@check_and_add_user
@send_typing_action
async def command_start_handler(message: Message):
    """Обработчик команды /start"""
    if not message.from_user:
        logger.warning("Получена команда /start без информации о пользователе")
        return

    user_name = (
        message.from_user.full_name or message.from_user.username or "Пользователь"
    )

    welcome_message = (
        f"👋 Привет, {user_name}!\n\n"
        f"Я Фрида - интеллектуальный помощник. Могу помочь вам найти информацию "
        f"и ответить на вопросы на основе загруженной базы знаний.\n\n"
        f"Просто напишите свой вопрос, и я постараюсь найти для вас релевантную информацию!"
    )

    try:
        await message.answer(welcome_message)
        logger.info(f"Пользователь {message.from_user.id} ({user_name}) запустил бота")
    except Exception as e:
        logger.error(f"Ошибка при отправке приветственного сообщения: {e}")
