import aiohttp
import asyncio
import logging
from config import UTILS_URL
from aiogram.types import Message
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def search_milvus(
    user_id: int,
    message: Message,  
) -> Optional[Dict[str, Any]]:
    params = {
        "user_id": user_id,
        "text": message.text if message else "", 
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(  
                f'{UTILS_URL}/v1/mlv_search',
                params=params 
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "combined_context": data.get("combined_context", ""),
                        "chat_history": data.get("chat_history", ""),
                        "hashs": data.get("hashs", [])
                    }
                
                elif response.status == 500:
                    error_data = await response.json()
                    logger.error(f"Server error: {error_data.get('error', 'Unknown error')}")
                    # if message:
                    #     await message.answer("⚠️ Ошибка на сервере при обработке запроса.")
                
                else:
                    text = await response.text()
                    logger.error(f"Unexpected status {response.status}: {text}")
                    # if message:
                    #     await message.answer("⚠️ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
                
                return None
                    
    except asyncio.TimeoutError:
        logger.error(f"[SearchService] Timeout while trying to reach {UTILS_URL}")
        # if message:
        #     await message.answer("⌛ Сервер не отвечает. Пожалуйста, попробуйте позже.")
        return None
        
    except aiohttp.ClientError as e:
        logger.error(f"[SearchService] Client error: {e}")
        # if message:
        #     await message.answer("⚠️ Ошибка соединения. Пожалуйста, попробуйте позже.")
        return None
        
    except Exception as e:
        logger.exception(f"[SearchService] Unexpected error: {e}")
        # if message:
        #     await message.answer("⚠️ Непредвиденная ошибка. Пожалуйста, попробуйте позже.")
        return None