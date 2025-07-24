"""
Обработчик общих сообщений пользователей.
Обеспечивает поиск контекста и генерацию ответов через AI API.
"""

import logging
from aiogram import Router
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.config import bot_config
from bot.api.log import log
from bot.handlers.tariff_handler import TariffQuestionForm
from bot.utils.helpers import (
    classify_and_process_query,
    handle_address_confirmation,
)
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

        # Используем новую функцию классификации и обработки запросов
        await classify_and_process_query(message.text, user_id, message)

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


# Обработчик callback-запросов для подтверждения адреса
@router.callback_query(F.data.startswith("addr_confirm_"))
@check_and_add_user
async def handle_address_confirm_callback(callback_query: CallbackQuery):
    """Обработка подтверждения адреса пользователем"""
    try:
        # Парсим callback_data: addr_confirm_{user_id}
        if not callback_query.data:
            await callback_query.answer("❌ Неверные данные")
            return

        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("❌ Неверные данные")
            return

        expected_user_id = int(parts[2])

        # Проверяем, что запрос от того же пользователя
        if callback_query.from_user and callback_query.from_user.id != expected_user_id:
            await callback_query.answer("❌ Это не ваш запрос")
            return

        await handle_address_confirmation(callback_query, True)

    except Exception as e:
        logger.exception(f"Ошибка при обработке подтверждения адреса: {e}")
        await callback_query.answer("❌ Произошла ошибка")


@router.callback_query(F.data.startswith("addr_reject_"))
@check_and_add_user
async def handle_address_reject_callback(callback_query: CallbackQuery):
    """Обработка отклонения адреса пользователем"""
    try:
        # Парсим callback_data: addr_reject_{user_id}
        if not callback_query.data:
            await callback_query.answer("❌ Неверные данные")
            return

        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("❌ Неверные данные")
            return

        expected_user_id = int(parts[2])

        # Проверяем, что запрос от того же пользователя
        if callback_query.from_user and callback_query.from_user.id != expected_user_id:
            await callback_query.answer("❌ Это не ваш запрос")
            return

        await handle_address_confirmation(callback_query, False)

    except Exception as e:
        logger.exception(f"Ошибка при обработке отклонения адреса: {e}")
        await callback_query.answer("❌ Произошла ошибка")


@router.callback_query(F.data.startswith("tariff_cancel_"))
@check_and_add_user
async def handle_tariff_cancel_callback(callback_query: CallbackQuery):
    """Обработка отмены выбора адреса"""
    try:
        # Парсим callback_data: tariff_cancel_{user_id}
        if not callback_query.data:
            await callback_query.answer("❌ Неверные данные")
            return

        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("❌ Неверные данные")
            return

        expected_user_id = int(parts[2])

        # Проверяем, что запрос от того же пользователя
        if callback_query.from_user and callback_query.from_user.id != expected_user_id:
            await callback_query.answer("❌ Это не ваш запрос")
            return

        # Очищаем сохраненный запрос
        from bot.utils.helpers import user_tariff_queries

        if expected_user_id in user_tariff_queries:
            del user_tariff_queries[expected_user_id]

        await callback_query.answer("Отменено")
        # Просто отвечаем на callback, не пытаемся редактировать сообщение

    except Exception as e:
        logger.exception(f"Ошибка при обработке отмены выбора адреса: {e}")
        await callback_query.answer("❌ Произошла ошибка")
