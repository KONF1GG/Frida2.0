"""
Базовый класс для HTTP клиентов API.
Обеспечивает единообразную обработку ошибок и логирование.
"""

import asyncio
import aiohttp
import logging
from abc import ABC
from typing import List, Literal, Optional, Dict, Any
from dataclasses import dataclass

from bot.config import bot_config

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Стандартизированный ответ API"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


class BaseAPIClient(ABC):
    """Базовый класс для всех API клиентов"""

    def __init__(self, base_url: str, timeout: int = 100):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Закрытие сессии"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """
        Выполнение HTTP запроса с обработкой ошибок

        Args:
            method: HTTP метод
            endpoint: Конечная точка API
            params: URL параметры
            json_data: JSON данные для тела запроса
            headers: HTTP заголовки

        Returns:
            APIResponse с результатом запроса
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            session = await self._get_session()

            async with session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers or {},
            ) as response:
                status_code = response.status

                # Успешный ответ
                if 200 <= status_code < 300:
                    try:
                        data = await response.json()
                        return APIResponse(
                            success=True, data=data, status_code=status_code
                        )
                    except aiohttp.ContentTypeError:
                        # Если ответ не JSON, возвращаем текст
                        text = await response.text()
                        return APIResponse(
                            success=True,
                            data={"response": text},
                            status_code=status_code,
                        )

                # Ошибка клиента или сервера
                else:
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get("error", f"HTTP {response.text}")
                    except aiohttp.ContentTypeError:
                        error_msg = await response.text()

                    # Для 404 ошибок в поиске адресов используем debug уровень
                    if status_code == 404 and "redis_addresses" in url:
                        query_param = (
                            params.get("query_address", "N/A") if params else "N/A"
                        )
                        logger.debug(f"Адрес не найден для запроса: {query_param}")
                    else:
                        logger.error(f"API error {status_code}: {error_msg}")

                    return APIResponse(
                        success=False, error=error_msg, status_code=status_code
                    )

        except asyncio.TimeoutError:
            error_msg = f"Timeout while requesting {url}"
            logger.error(error_msg)
            return APIResponse(success=False, error=error_msg)

        except aiohttp.ClientError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            return APIResponse(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(error_msg)
            return APIResponse(success=False, error=error_msg)

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """GET запрос"""
        return await self._make_request("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """POST запрос"""
        return await self._make_request(
            "POST", endpoint, params=params, json_data=json_data, headers=headers
        )


class UtilsAPIClient(BaseAPIClient):
    """Клиент для работы с Utils API"""

    def __init__(self):
        super().__init__(base_url=bot_config.utils_url)

    async def search_milvus(self, user_id: int, text: str) -> APIResponse:
        """Поиск в Milvus"""
        return await self.get(
            "v1/mlv_search", params={"user_id": user_id, "text": text}
        )

    async def call_ai(
        self,
        text: str,
        combined_context: str,
        chat_history: str = "",
        input_type: str = "text",
        model: str = "mistral-large-latest",
    ) -> APIResponse:
        """Вызов AI API"""
        return await self.post(
            "v1/ai",
            json_data={
                "text": text,
                "combined_context": combined_context,
                "chat_history": chat_history,
                "input_type": input_type,
                "model": model,
            },
        )

    async def log_message(
        self,
        user_id: int,
        query: str,
        ai_response: str,
        status: Literal[1, 0],
        hashes: List[str],
        category: str = "Общий",
    ) -> APIResponse:
        """Логирование сообщения"""
        return await self.post(
            "v1/log",
            json_data={
                "user_id": user_id,
                "query": query,
                "ai_response": ai_response,
                "status": status,
                "hashes": hashes,
                "category": category,
            },
        )

    async def upload_wiki_data(self, user_id: int) -> APIResponse:
        """Загрузка данных Wiki"""
        return await self.post("v1/upload_wiki_data", json_data={"user_id": user_id})

    async def register_user(
        self, user_id: int, firstname: str, lastname: str, username: str
    ) -> APIResponse:
        """Регистрация пользователя"""
        return await self.post(
            "v1/auth",
            json_data={
                "user_id": user_id,
                "firstname": firstname,
                "lastname": lastname or "",
                "username": username or "",
            },
        )

    async def get_admins(self) -> APIResponse:
        """Получение списка администраторов"""
        return await self.get("v1/admins")

    async def get_addresses_from_redis(self, query_address: str) -> APIResponse:
        """Получение списка адресов"""
        return await self.get(
            "redis_addresses", params={"query_address": query_address}
        )

    async def get_address_by_id(self, address_id: str) -> APIResponse:
        """Получение адреса по ID"""
        return await self.get("redis_address_by_id", params={"address_id": address_id})

    async def get_tariffs_from_redis(self, territory_id: str) -> APIResponse:
        """Получение тарифов для определенного territory_id"""
        return await self.get("redis_tariffs", params={"territory_id": territory_id})


# Глобальный экземпляр клиента
utils_client = UtilsAPIClient()
