"""
Клиент для работы с AI API.
Обеспечивает вызов модели с обработкой ошибок.
"""

import logging
from typing import Optional, Literal

from .base import utils_client

logger = logging.getLogger(__name__)


async def call_ai(
    text: str,
    combined_context: str,
    chat_history: Optional[str] = "",
    input_type: Literal["voice", "csv", "text"] = "text",
    model: str = "mistral",  # Добавляем параметр модели
) -> Optional[str]:
    """
    Вызов AI API для генерации ответа

    Args:
        text: Текст запроса пользователя
        combined_context: Контекст из базы знаний
        chat_history: История чата
        input_type: Тип входных данных
        model: Модель AI (mistral, deepseek, gpt)

    Returns:
        Ответ от AI или None в случае ошибки
    """
    try:
        response = await utils_client.call_ai(
            text=text,
            combined_context=combined_context,
            chat_history=chat_history or "",
            input_type=input_type,
            model=model,
        )

        if response.success and response.data:
            return response.data.get("ai_response", "")

        else:
            logger.error(f"AI API error: {response.error}")
            return None

    except Exception as e:
        logger.exception(f"Unexpected error in call_ai: {e}")
        return None
