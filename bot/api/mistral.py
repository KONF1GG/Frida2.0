import aiohttp
import asyncio
import logging
from config import UTILS_URL
from aiogram.types import Message
from typing import Dict, Any, Literal, Optional

logger = logging.getLogger(__name__)


async def call_mistral(
    text: str,
    combined_context: str,
    chat_history: Optional[str] = "",
    message: Optional[Any] = None,
    input_type: Literal['voice', 'csv', 'text'] = 'text'
) -> Optional[str]:
    params = {
        "text": text,
        "combined_context": combined_context,
        "chat_history": chat_history,
        "input_type": input_type,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f'{UTILS_URL}/v1/mistral',
                params=params
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return data.get("mistral_response", "")
                
                elif response.status == 500:
                    error_data = await response.json()
                    logger.error(f"Mistral API error: {error_data.get('error', 'Unknown error')}")
                    # if message:
                    #     await message.answer("⚠️ Ошибка в работе модели Mistral.")
                
                else:
                    error_text = await response.text()
                    logger.error(f"Unexpected status {response.status}: {error_text}")
                    # if message:
                    #     await message.answer("⚠️ Ошибка при обработке запроса.")
                
                return None
                    
    except asyncio.TimeoutError:
        logger.error(f"[MistralService] Timeout while trying to reach {UTILS_URL}")
        # if message:
        #     await message.answer("⌛ Сервер Mistral не отвечает. Попробуйте позже.")
        return None
        
    except aiohttp.ClientError as e:
        logger.error(f"[MistralService] Connection error: {e}")
        # if message:
        #     await message.answer("⚠️ Ошибка соединения с Mistral.")
        return None
        
    except Exception as e:
        logger.exception(f"[MistralService] Unexpected error: {e}")
        # if message:
        #     await message.answer("⚠️ Непредвиденная ошибка в Mistral API.")
        return None