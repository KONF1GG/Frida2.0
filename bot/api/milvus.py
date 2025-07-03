"""
Клиент для работы с Milvus векторной базой данных.
Обеспечивает поиск релевантного контекста и истории чата.
"""

import logging
from typing import Dict, Any, Optional
from aiogram.types import Message

from .base import utils_client

logger = logging.getLogger(__name__)


async def search_milvus(
    user_id: int,
    message: Message,
) -> Optional[Dict[str, Any]]:
    """
    Поиск релевантного контекста в Milvus

    Args:
        user_id: ID пользователя
        message: Сообщение пользователя

    Returns:
        Словарь с контекстом и историей или None в случае ошибки
    """
    try:
        response = await utils_client.search_milvus(
            user_id=user_id, text=message.text or "" if message else ""
        )

        if response.success and response.data:
            return {
                "combined_context": response.data.get("combined_context", ""),
                "chat_history": response.data.get("chat_history", ""),
                "hashs": response.data.get("hashs", []),
            }

        else:
            logger.error(f"Milvus search error: {response.error}")
            return None

    except Exception as e:
        logger.exception(f"Unexpected error in search_milvus: {e}")
        return None
