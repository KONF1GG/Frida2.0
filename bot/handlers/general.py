"""
Обработчик общих сообщений пользователей.
Обеспечивает поиск контекста и генерацию ответов через AI API.
"""

import logging
from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.config import bot_config
from bot.api.milvus import search_milvus
from bot.api.ai import call_ai
from bot.api.log import log
from bot.handlers.models import user_model
from bot.handlers.tariff_handler import TariffQuestionForm
from aiogram import F

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.startswith("@"))
@check_and_add_user
@send_typing_action
async def handle_at_message(message: Message, state: FSMContext):
    """Обработка сообщений, начинающихся с @"""
    if not message.text or not message.from_user:
        logger.warning("Получено сообщение без текста или пользователя")
        return

    # Получаем username бота для создания кнопки
    try:
        bot_info = await message.bot.me()  # type: ignore
        bot_username = bot_info.username if bot_info and bot_info.username else "bot"
    except Exception:
        bot_username = "bot"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Начать поиск тарифов", switch_inline_query_current_chat=""
                )
            ]
        ]
    )

    await message.answer(
        "🤔 <b>Похоже, вы пытались воспользоваться инлайн-режимом для поиска тарифов!</b>\n\n"
        "📋 <i>Для корректной работы необходимо:</i>\n"
        "1️⃣ Нажать кнопку ниже для входа в инлайн-режим\n"
        "2️⃣ Выбрать нужный адрес из выпадающего списка\n"
        "3️⃣ После выбора адреса задать свой вопрос\n\n"
        f"Нажмите кнопку ниже — в строке ввода появится <code>@{bot_username} </code> и вы сможете сразу ввести адрес для поиска информации по тарифам.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.message()
@check_and_add_user
@send_typing_action
async def message_handler(message: Message, state: FSMContext):
    """Обработка обычных сообщений пользователей с отображением модели."""
    if not message.text or not message.from_user:
        logger.warning("Получено сообщение без текста или пользователя")
        return

    # Проверяем, не находится ли пользователь в тарифном режиме
    current_state = await state.get_state()
    if current_state in [
        TariffQuestionForm.waiting_for_question,
        TariffQuestionForm.in_tariff_mode,
    ]:
        # Если пользователь в тарифном режиме, не обрабатываем здесь
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
