"""
Обработчик общих сообщений пользователей.
Обеспечивает поиск контекста и генерацию ответов через AI API.
"""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode

from utils.decorators import check_and_add_user, send_typing_action
from config import bot_config
from api.milvus import search_milvus
from bot.api.ai import call_ai
from api.log import log
from bot.handlers.models import user_model

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message()
@check_and_add_user
@send_typing_action
async def message_handler(message: Message):
    """Обработка обычных сообщений пользователей."""
    if not message.text or not message.from_user:
        logger.warning("Получено сообщение без текста или пользователя")
        return

    user_id = message.from_user.id

    try:
        loading_message = await message.answer_sticker(bot_config.loading_sticker)

        # Поиск релевантного контекста
        search_result = await search_milvus(user_id, message)

        if not search_result:
            logger.error(
                f"Не удалось получить результаты поиска для пользователя {user_id}"
            )
            await message.answer(
                "⚠️ Прошу прощения, произошла ошибка при поиске информации. Попробуйте позже..."
            )
            return

        # Генерация ответа через AI API
        ai_response = await call_ai(
            text=message.text,
            combined_context=search_result.get("combined_context", ""),
            chat_history=search_result.get("chat_history", ""),
            model=user_model.get(user_id, "mistral-large-latest"),
        )

        if ai_response:
            await message.answer(ai_response, parse_mode=ParseMode.HTML)
            # Логирование успешного запроса
            await log(
                user_id=user_id,
                query=message.text,
                ai_response=ai_response,
                status=1,
                hashes=search_result.get("hashs", []),
            )
            logger.info(f"Успешно обработан запрос пользователя {user_id}")
        else:
            error_message = "⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже..."
            await message.answer(error_message, parse_mode=ParseMode.HTML)
            # Логирование неудачного запроса
            await log(
                user_id=user_id,
                query=message.text,
                ai_response=error_message,
                status=0,
                hashes=search_result.get("hashs", []),
            )
            logger.warning(f"AI не смог обработать запрос пользователя {user_id}")

    except Exception as e:
        error_message = (
            "⚠️ Прошу прощения, произошла непредвиденная ошибка. Попробуйте позже..."
        )
        logger.exception(f"Ошибка при обработке сообщения пользователя {user_id}: {e}")

        try:
            await message.answer(error_message, parse_mode=ParseMode.HTML)
            # Логирование ошибки
            await log(
                user_id=user_id,
                query=message.text,
                ai_response=str(e),
                status=0,
                hashes=[],
            )
        except Exception as log_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {log_error}")

    finally:
        try:
            await loading_message.delete()
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить loading message: {delete_error}")
