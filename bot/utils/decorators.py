"""
Декораторы для обработчиков сообщений.
Обеспечивают аутентификацию пользователей и отправку статусов действий.
"""

from functools import wraps
import logging
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction

from api.auth import check_and_register_user

logger = logging.getLogger(__name__)


def check_and_add_user(func):
    """
    Декоратор для проверки и регистрации пользователя в системе

    Args:
        func: Обработчик сообщения

    Returns:
        Wrapped функция с проверкой пользователя
    """

    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if not message.from_user:
            logger.warning("Сообщение получено без информации о пользователе")
            return None

        user = message.from_user

        try:
            success = await check_and_register_user(
                user_id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username or "",
                message=message,
            )

            if not success:
                logger.warning(f"Не удалось зарегистрировать пользователя {user.id}")
                return None

            return await func(message, *args, **kwargs)

        except Exception as e:
            logger.exception(
                f"Ошибка в декораторе check_and_add_user для пользователя {user.id}: {e}"
            )
            try:
                await message.answer(
                    "⚠️ Произошла ошибка при аутентификации. Попробуйте позже."
                )
            except Exception as msg_error:
                logger.error(
                    f"Не удалось отправить сообщение об ошибке аутентификации: {msg_error}"
                )
            return None

    return wrapper


def send_typing_action(func):
    """
    Декоратор для отправки статуса "печатает" во время обработки сообщения

    Args:
        func: Обработчик сообщения

    Returns:
        Wrapped функция с отправкой статуса печатания
    """

    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        try:
            if message.bot:
                await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        except Exception as e:
            logger.warning(f"Не удалось отправить статус печатания: {e}")

        return await func(message, *args, **kwargs)

    return wrapper
