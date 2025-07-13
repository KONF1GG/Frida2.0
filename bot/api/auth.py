"""
Клиент для аутентификации и управления пользователями.
Обеспечивает регистрацию пользователей и получение информации об администраторах.
"""

from typing import Dict, List, Optional
import logging
from aiogram.types import Message

from .base import utils_client

logger = logging.getLogger(__name__)


async def check_and_register_user(
    user_id: int,
    first_name: str,
    last_name: str,
    username: str,
    message: Optional[Message] = None,
) -> bool:
    """
    Проверка и регистрация пользователя

    Args:
        user_id: ID пользователя
        first_name: Имя пользователя
        last_name: Фамилия пользователя
        username: Имя пользователя в Telegram
        message: Сообщение для отправки ошибок (опционально)

    Returns:
        True в случае успешной регистрации/проверки, False иначе
    """
    try:
        response = await utils_client.register_user(
            user_id=user_id,
            firstname=first_name,
            lastname=last_name or "",
            username=username or "",
        )

        if response.success:
            logger.info(f"User {user_id} checked/added successfully.")
            return True
        elif response.status_code == 403:
            if message:
                await message.answer(
                    "Кажется, вы не являетесь сотрудником компании Фридом. "
                    'Если это не так, обратитесь, пожалуйста, к <a href="https://t.me/Leontykro">@Leontykro</a>.',
                    parse_mode="HTML",
                )
            return False
        else:
            logger.error(f"Auth error: {response.error}")
            if message:
                await message.answer(
                    "⚠️ Произошла ошибка при обращении к серверу. Пожалуйста, попробуйте позже."
                )
            return False

    except Exception as e:
        logger.exception(f"Unexpected error in check_and_register_user: {e}")
        if message:
            await message.answer(
                "⚠️ Непредвиденная ошибка. Пожалуйста, попробуйте позже."
            )
        return False


async def get_admins() -> List[Dict[str, str]]:
    """
    Получает список администраторов через API

    Returns:
        Список администраторов в формате [{"user_id": int, "username": str}]

    Raises:
        RuntimeError: Если произошла ошибка при запросе к API
        ValueError: Если получены некорректные данные
    """
    try:
        response = await utils_client.get_admins()

        if response.success and response.data:
            admins = response.data
            if not isinstance(admins, list):
                raise ValueError("Некорректный формат данных администраторов")
            return admins
        else:
            raise RuntimeError(f"API error: {response.data}")

    except Exception as e:
        raise RuntimeError(f"Unexpected error: {str(e)}")
