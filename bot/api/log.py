import aiohttp
import asyncio
import logging
from config import UTILS_URL
from aiogram.types import Message
from typing import Dict, Any, List, Literal, Optional
import json

logger = logging.getLogger(__name__)

async def log(
    user_id: str,
    query: str,
    mistral_response: str,
    status: Literal[1, 0],
    hashes: List[str],
):
    params = {
        "user_id": user_id,
        "query": query,
        "mistral_response": mistral_response,
        "status": status,
        "hashes": hashes,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f'{UTILS_URL}/v1/log',
                json=params, 
                headers={'Content-Type': 'application/json'} 
            ) as response:
                
                if response.status == 200:
                    return True
                
                elif response.status == 500:
                    error_data = await response.json()
                    logger.error(f"Log error: {error_data.get('error', 'Unknown error')}")
                else:
                    error_text = await response.text()
                    logger.error(f"Unexpected status {response.status}: {error_text}")
                
                return None
                    
    except asyncio.TimeoutError:
        logger.error(f"[Logger] Timeout while trying to reach {UTILS_URL}")
        return None
        
    except aiohttp.ClientError as e:
        logger.error(f"[Logger] Connection error: {e}")
        return None
        
    except Exception as e:
        logger.exception(f"[Logger] Unexpected error: {e}")
        return None