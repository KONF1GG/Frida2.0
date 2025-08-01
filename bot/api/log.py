"""
Клиент для логирования сообщений пользователей.
Отправляет логи в центральную систему для анализа.
"""

import logging
from typing import List, Literal

from .base import core_client

logger = logging.getLogger(__name__)


async def log(
    user_id: int,
    query: str,
    ai_response: str,
    status: Literal[1, 0],
    hashes: List[str],
    category: str = "Общий",
) -> bool:
    """
    Логирование сообщения пользователя

    Args:
        user_id: ID пользователя
        query: Запрос пользователя
        ai_response: Ответ AI
        status: Статус обработки (1 - успех, 0 - ошибка)
        hashes: Список хешей релевантных документов
        category: Категория запроса (Тарифы, Общий, и т.д.)

    Returns:
        True в случае успешного логирования, False иначе
    """
    try:
        response = await core_client.log_message(
            user_id=user_id,
            query=query,
            ai_response=ai_response,
            status=status,
            hashes=hashes,
            category=category,
        )

        if response.success:
            return True
        else:
            logger.error(f"Log error: {response.error}")
            return False

    except Exception as e:
        logger.exception(f"Unexpected error in log: {e}")
        return False
