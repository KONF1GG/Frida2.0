from typing import Dict, List
import aiohttp
import asyncio
import logging
from config import UTILS_URL
from aiogram.types import Message
logger = logging.getLogger(__name__)


async def check_and_register_user(
    user_id: int, 
    first_name: str, 
    last_name: str, 
    username: str,
    message: Message = None 
) -> bool:
    params = {
        "user_id": user_id,
        "firstname": first_name,
        "lastname": last_name or "",
        "username": username or ""
    }

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f'{UTILS_URL}/v1/auth',
                json=params
            ) as response:
                if response.status == 200:
                    logger.info(f"[AuthService] User {user_id} checked/added successfully.")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"[AuthService] Error {response.status}: {text}")
                    if message:
                        await message.answer("⚠️ Произошла ошибка при обращении к серверу. Пожалуйста, попробуйте позже.")
                    return False
                    
    except asyncio.TimeoutError:
        logger.error(f"[AuthService] Timeout while trying to reach {UTILS_URL}")
        if message:
            await message.answer("⌛ Сервер не отвечает. Пожалуйста, попробуйте позже.")
        return False
        
    except aiohttp.ClientError as e:
        logger.error(f"[AuthService] Client error: {e}")
        if message:
            await message.answer("⚠️ Ошибка соединения. Пожалуйста, попробуйте позже.")
        return False
        
    except Exception as e:
        logger.exception(f"[AuthService] Unexpected error: {e}")
        if message:
            await message.answer("⚠️ Непредвиденная ошибка. Пожалуйста, попробуйте позже.")
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
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{UTILS_URL}/v1/admins',
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    admins = await response.json()
                    if not isinstance(admins, list):
                        raise ValueError("Некорректный формат данных администраторов")
                    return admins
                
                error_text = await response.text()
                raise RuntimeError(
                    f"Ошибка сервера (HTTP {response.status}): {error_text}"
                )
                
    except aiohttp.ClientError as e:
        raise RuntimeError(f"Ошибка соединения: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Непредвиденная ошибка: {str(e)}")

    
