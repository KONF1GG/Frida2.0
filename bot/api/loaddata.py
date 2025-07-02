import aiohttp
from config import UTILS_URL
from typing import Dict, Any

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
    data = {"user_id": user_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{UTILS_URL}/v1/upload_wiki_data', 
                json=data,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                
                # Обработка успешного ответа
                if response.status == 200:
                    result = await response.json()
                    return {
                        "status": "success",
                        "message": "Данные успешно загружены",
                        "data": result
                    }
                
                # Обработка ошибки прав доступа
                elif response.status == 403:
                    error_detail = await response.text()
                    raise RuntimeError(
                        f"Ошибка доступа: {error_detail}. "
                        f"Пользователь {user_id} не имеет прав администратора"
                    )
                
                # Обработка других ошибок сервера
                elif response.status >= 400:
                    error_detail = await response.text()
                    raise RuntimeError(
                        f"Ошибка сервера (HTTP {response.status}): {error_detail}"
                    )
                
                # Обработка неожиданных кодов ответа
                else:
                    raise ValueError(
                        f"Получен неожиданный код ответа: {response.status}"
                    )

    except aiohttp.ClientError as e:
        raise RuntimeError(f"Ошибка соединения с сервером: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Непредвиденная ошибка при загрузке данных: {str(e)}")