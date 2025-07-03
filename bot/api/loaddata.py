"""
Клиент для загрузки данных Wiki в Milvus.
Обеспечивает загрузку и обработку данных из Wiki источников.
"""

import logging
from typing import Dict, Any

from .base import utils_client

logger = logging.getLogger(__name__)


class LoadDataClient:
    """Клиент для загрузки различных типов данных в базу знаний"""

    async def load_text_data(self, title: str, text: str, user_id: int) -> bool:
        """
        Загружает текстовые данные в базу знаний

        Args:
            title: Заголовок документа
            content: Содержимое документа

        Returns:
            True если загрузка успешна, False иначе
        """
        try:
            # Формируем данные для отправки
            data = {"title": title, "text": text, "user_id": user_id}

            response = await utils_client.post("/v1/add_topic", json_data=data)

            if response.success:
                logger.info(f"Текстовые данные успешно загружены: {title}")
                return True
            else:
                logger.error(f"Ошибка загрузки текстовых данных: {response.error}")
                return False

        except Exception as e:
            logger.error(f"Исключение при загрузке текстовых данных: {e}")
            return False

    def _get_mime_type(self, file_type: str) -> str:
        """Возвращает MIME тип для файла"""
        mime_types = {
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        return mime_types.get(file_type.lower(), "application/octet-stream")


async def upload_wiki_data(user_id: int) -> Dict[str, Any]:
    """
    Загружает данные wiki в Milvus через API

    Args:
        user_id: ID пользователя, инициирующего загрузку

    Returns:
        Словарь с результатом операции:
        {
            "status": "success"|"error",
            "message": str,
            "data": dict|None
        }

    Raises:
        ValueError: Если получен некорректный ответ от сервера
        RuntimeError: Если произошла ошибка при загрузке данных
    """
    try:
        response = await utils_client.upload_wiki_data(user_id)

        if response.success:
            return {
                "status": "success",
                "message": "Данные успешно загружены",
                "data": response.data,
            }

        # Обработка ошибки прав доступа
        elif response.status_code == 403:
            raise RuntimeError(
                f"Ошибка доступа: {response.error}. "
                f"Пользователь {user_id} не имеет прав администратора"
            )

        # Обработка других ошибок
        else:
            raise RuntimeError(f"Ошибка сервера: {response.error}")

    except RuntimeError:
        # Пробрасываем RuntimeError дальше
        raise
    except Exception as e:
        raise RuntimeError(f"Непредвиденная ошибка при загрузке данных: {str(e)}")
