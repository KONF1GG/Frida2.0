"""
Декораторы для обработчиков сообщений.
Обеспечивают аутентификацию пользователей и отправку статусов действий.
"""

from functools import wraps
import logging
from aiogram.enums.chat_action import ChatAction

from bot.api.auth import check_and_register_user

logger = logging.getLogger(__name__)


def check_and_add_user(func):
    """
    Декоратор для проверки и регистрации пользователя в системе
    Работает как с Message, так и с InlineQuery

    Args:
        func: Обработчик сообщения

    Returns:
        Wrapped функция с проверкой пользователя
    """

    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        # Получаем пользователя из разных типов событий
        user = None
        if hasattr(event, "from_user"):
            user = event.from_user

        if not user:
            logger.warning("Событие получено без информации о пользователе")
            return None

        try:
            success = await check_and_register_user(
                user_id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username or "",
                message=event if hasattr(event, "chat") else None,
            )

            if not success:
                logger.warning(f"Не удалось зарегистрировать пользователя {user.id}")
                return None

            return await func(event, *args, **kwargs)

        except Exception as e:
            logger.exception(
                f"Ошибка в декораторе check_and_add_user для пользователя {user.id}: {e}"
            )
            try:
                # Отправляем ошибку только для обычных сообщений, не для inline запросов
                if hasattr(event, "answer") and hasattr(event, "chat"):
                    await event.answer(
                        "⚠️ Произошла ошибка при аутентификации. Попробуйте позже."
                    )
                elif hasattr(event, "answer") and not hasattr(event, "chat"):
                    # Для inline запросов
                    await event.answer(
                        [],
                        cache_time=1,
                        switch_pm_text="Ошибка аутентификации",
                        switch_pm_parameter="auth_error",
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
    Работает только с Message объектами, игнорирует InlineQuery

    Args:
        func: Обработчик сообщения

    Returns:
        Wrapped функция с отправкой статуса печатания
    """

    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        try:
            # Проверяем, что это Message объект, а не InlineQuery
            if hasattr(event, "chat") and hasattr(event, "bot") and event.bot:
                await event.bot.send_chat_action(event.chat.id, ChatAction.TYPING)
        except Exception as e:
            logger.warning(f"Не удалось отправить статус печатания: {e}")

        return await func(event, *args, **kwargs)

    return wrapper
