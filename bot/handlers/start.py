"""
Обработчик команды /start.
Приветствует пользователя и регистрирует его в системе.
"""

import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.api.log import log

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
@check_and_add_user
@send_typing_action
async def command_start_handler(message: Message):
    """Обработчик команды /start"""
    logger.debug("🚀 Получена команда /start")

    if not message.from_user:
        logger.warning("Получена команда /start без информации о пользователе")
        return

    user_name = (
        message.from_user.full_name or message.from_user.username or "Пользователь"
    )

    logger.info(
        f"👤 Пользователь {message.from_user.id} ({user_name}) запустил команду /start"
    )

    welcome_message = (
        f"👋 Привет, {user_name}!\n\n"
        f"Я <b>Фрида</b> - интеллектуальный помощник. Могу помочь вам найти информацию "
        f"и ответить на вопросы на основе загруженной базы знаний.\n\n"
        f"🔍 <b>Что я умею:</b>\n"
        f"• Отвечать на вопросы по базе знаний\n"
        f"• Искать информацию о тарифах по адресам\n"
        f"• Анализировать файлы (PDF, Word, Excel)\n"
        f"• Работать с голосовыми сообщениями\n\n"
        f"💡 Просто напишите свой вопрос, и я постараюсь найти для вас релевантную информацию!\n\n"
        f"📋 Для просмотра всех команд введите /help"
    )

    try:
        logger.debug("📤 Отправляем приветственное сообщение...")
        await message.answer(welcome_message, parse_mode="HTML")
        logger.info(
            f"✅ Приветственное сообщение отправлено пользователю {message.from_user.id}"
        )

        # Логируем команду start
        logger.debug("📝 Записываем лог команды /start...")
        await log(
            user_id=message.from_user.id,
            query="/start",
            ai_response=welcome_message,
            status=1,
            hashes=[],
            category="Команда",
        )
        logger.debug("✅ Лог команды /start записан")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке приветственного сообщения: {e}")

        # Логируем ошибку
        await log(
            user_id=message.from_user.id,
            query="/start",
            ai_response=str(e),
            status=0,
            hashes=[],
            category="Команда",
        )
