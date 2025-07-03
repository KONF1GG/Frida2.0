from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
import logging
from utils.user_settings import MODEL_MAPPING, user_model

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

def _get_model_keyboard(current: str) -> InlineKeyboardMarkup:
    """Клавиатура для выбора модели с галочкой у выбранной"""
    buttons = []
    for key, label in [
        ("mistral", "Mistral"),
        ("gpt", "GPT"),
        ("deepseek", "DeepSeek"),
    ]:
        prefix = "✅ " if MODEL_MAPPING.get(key) == current else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"set_model:{key}"
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


@router.message(Command("model"))
async def command_model(message: Message):
    """Обработчик команды /model"""
    if not message or not message.from_user:
        logger.warning("Получена команда /model без сообщения или пользователя")
        return

    current = user_model.get(message.from_user.id, "mistral-large-latest")
    await message.answer(
        "Пожалуйста, выберите модель для обработки запросов:",
        reply_markup=_get_model_keyboard(current)
    )


@router.callback_query(F.data.startswith("set_model:"))
async def callback_set_model(call: CallbackQuery):
    """Установка выбранной модели"""
    if not call or not call.data:
        logger.warning("Получен пустой callback query")
        return
        
    if not call.from_user:
        logger.warning("Callback query без информации о пользователе")
        return
        
    try:
        parts = call.data.split(":")
        if len(parts) != 2:
            logger.warning(f"Неверный формат callback data: {call.data}")
            return
            
        _, chosen = parts
        selected_model = MODEL_MAPPING.get(chosen, "mistral-large-latest")
        user_model[call.from_user.id] = selected_model
        
        # Отправляем уведомление
        await call.answer(f"Модель изменена на {chosen.upper()}", show_alert=False)
        
        # Обновляем сообщение, если возможно
        if call.message:
            try:
                model_name_display = {
                    "mistral-large-latest": "Mistral",
                    "gpt-4o-mini": "GPT",
                    "deepseek/deepseek-chat-v3-0324:free": "DeepSeek"
                }.get(selected_model, selected_model)

                await call.message.edit_text(
                    f"✅ Вы выбрали модель: <b>{model_name_display}</b>",
                    reply_markup=_get_model_keyboard(selected_model),
                    parse_mode="HTML"
                )
                logger.info(f"Пользователь {call.from_user.id} выбрал модель {selected_model}")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                if "message is not modified" in str(e).lower():
                    pass 
                else:
                    try:
                        await call.message.answer(f"✅ Вы выбрали модель: <b>{model_name_display}</b>", parse_mode="HTML")
                    except Exception as msg_e:
                        logger.error(f"Не удалось отправить сообщение: {msg_e}")
        else:
            logger.warning("Callback message is None, невозможно обновить")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора модели: {e}")
