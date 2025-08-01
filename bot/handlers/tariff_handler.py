"""Обработчик сообщений territoryId"""

import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.api.base import core_client
from bot.config import bot_config

from bot.api.ai import call_ai
from bot.api.log import log
from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.utils.user_settings import user_model

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


class TariffQuestionForm(StatesGroup):
    waiting_for_question = State()
    in_tariff_mode = State()


@router.message(F.text.startswith("terId"))
@check_and_add_user
@send_typing_action
async def handle_tariff_message(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    tariff_code = message.text
    if tariff_code is None:
        await message.answer("⚠️ Что-то пошло не так. Попробуйте позже")
        return

    terr_id = tariff_code.split("_")[1]
    api_response = await core_client.get_tariffs_from_redis(terr_id)

    if not api_response.success or not api_response.data:
        await message.answer("⚠️ Что-то пошло не так. Попробуйте позже")
        return

    tariff_info = api_response.data

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Поиск тарифов", switch_inline_query_current_chat=""
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="cancel_tariff_question"
                ),
            ]
        ]
    )

    sent_message = await message.answer(
        f"✅ <b>Информация о тарифах найдена!</b>\n\n"
        f"Код территории: <code>{terr_id}</code>\n\n"
        f"Теперь вы можете задать вопрос по данному адресу. "
        f'Например: <i>"Какая стоимость подключения?"</i> или <i>"Какие тарифы доступны?"</i>\n\n'
        f"💬 <b>Введите ваш вопрос:</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    await state.update_data(
        tariff_info=tariff_info,
        territory_id=terr_id,
        chat_history="",
        initial_message_id=sent_message.message_id,  # Сохраняем ID сообщения
    )
    await state.set_state(TariffQuestionForm.waiting_for_question)


@router.callback_query(F.data == "cancel_tariff_question")
@check_and_add_user
@send_typing_action
async def cancel_tariff_question(callback, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text("❌ Запрос отменен")


@router.message(TariffQuestionForm.waiting_for_question)
async def process_tariff_question(message: Message, state: FSMContext):
    if message.text is None or not message.text.strip():
        await message.answer("⚠️ Непредвиденная ошибка: сообщение не содержит текста.")
        return

    data = await state.get_data()
    tariff_info = data.get("tariff_info", "")
    territory_id = data.get("territory_id", "")
    chat_history = data.get("chat_history", "")
    initial_message_id = data.get("initial_message_id")  # ID сообщения с кнопкой отмены

    # Убираем кнопку "❌ Отмена" из предыдущего сообщения
    if initial_message_id and message.bot:
        try:
            await message.bot.edit_message_text(  # type: ignore
                chat_id=message.chat.id,
                message_id=initial_message_id,
                text=f"✅ <b>Информация о тарифах найдена!</b>\n\n"
                f"Код территории: <code>{territory_id}</code>\n\n"
                f"💬 <b>Вопрос принят к обработке...</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")

    await state.set_state(TariffQuestionForm.in_tariff_mode)

    try:
        loading_message = await message.answer_sticker(bot_config.loading_sticker)

        if message.from_user is None:
            await message.answer("⚠️ Непредвиденная ошибка: пользователь не найден.")
            return

        selected_model = user_model.get(message.from_user.id, "mistral-large-latest")

        tariff_context = (
            f"Информация о тарифах для территории {territory_id}:\n{str(tariff_info)}"
        )

        ai_response = await call_ai(
            text=message.text,
            combined_context=tariff_context,
            chat_history=chat_history,
            model=selected_model,
        )

        if ai_response:
            new_history = f"{chat_history}\nПользователь: {message.text}\nАссистент: {ai_response}"
            await state.update_data(chat_history=new_history)

            status_bar = f"📍 Территория: {territory_id}\n\n"

            await message.answer(status_bar + ai_response, parse_mode="HTML")

            # Логируем успешный ответ
            await log(
                user_id=message.from_user.id,
                query=message.text,
                ai_response=ai_response,
                status=1,
                hashes=[],
                category="Тарифы",
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🏠 Продолжить по тарифам",
                            callback_data="continue_tariff",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="💬 Обычный режим", callback_data="switch_to_general"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Завершить", callback_data="end_conversation"
                        )
                    ],
                ]
            )

            await message.answer(
                "<i>Выберите режим для следующего вопроса:</i>",
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            logger.info(
                f"Успешно обработан тарифный запрос пользователя {message.from_user.id}"
            )
        else:
            error_msg = (
                "⚠️ Произошла ошибка при обработке вашего вопроса. Попробуйте позже."
            )
            await message.answer(error_msg)

            # Логируем ошибку
            await log(
                user_id=message.from_user.id,
                query=message.text,
                ai_response=error_msg,
                status=0,
                hashes=[],
                category="Тарифы",
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке тарифного вопроса: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке вашего вопроса. Попробуйте позже."
        )

    finally:
        try:
            await loading_message.delete()
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить loading message: {delete_error}")


@router.callback_query(F.data == "continue_tariff")
@check_and_add_user
@send_typing_action
async def continue_tariff_mode(callback, state: FSMContext):
    await callback.answer("Продолжаем в тарифном режиме")

    # Создаем клавиатуру только с кнопкой "Назад"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_to_mode_selection"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💬 <b>Задайте следующий вопрос по тарифам:</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(TariffQuestionForm.waiting_for_question)


@router.callback_query(F.data == "back_to_mode_selection")
@check_and_add_user
@send_typing_action
async def back_to_mode_selection(callback, state: FSMContext):
    await callback.answer("Возвращаемся к выбору режима")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Продолжить по тарифам",
                    callback_data="continue_tariff",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Обычный режим", callback_data="switch_to_general"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Завершить", callback_data="end_conversation"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "<i>Выберите режим для следующего вопроса:</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "switch_to_general")
@check_and_add_user
@send_typing_action
async def switch_to_general_mode(callback, state: FSMContext):
    await state.clear()
    await callback.answer("Переключено в обычный режим")
    await callback.message.edit_text(
        "💬 <b>Обычный режим активирован</b>\n\n"
        "Теперь ваши вопросы будут обрабатываться через векторную базу знаний. "
        "Просто напишите ваш вопрос.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "end_conversation")
@check_and_add_user
@send_typing_action
async def end_conversation(callback, state: FSMContext):
    await state.clear()
    await callback.answer("Разговор завершен")
    await callback.message.edit_text("✅ Разговор завершен. Спасибо за обращение!")
