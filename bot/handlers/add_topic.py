"""
Обработчик команды /addtopic для добавления новых тем в базу знаний.
Полнофункциональная реализация с пошаговым вводом данных.
"""

import logging
from typing import Union

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Document,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.exceptions import TelegramBadRequest

from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.utils.helpers import process_document
from bot.utils.states import AddTopicForm
from bot.api.loaddata import LoadDataClient

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# Инициализация клиентов
loaddata_client = LoadDataClient()


def get_input_method_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора способа ввода данных"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Ввести текст вручную", callback_data="addtopic_manual"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📄 Загрузить файл", callback_data="addtopic_file"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="addtopic_cancel")],
        ]
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения загрузки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить", callback_data="addtopic_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить заголовок", callback_data="addtopic_edit_title"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="addtopic_cancel")],
        ]
    )


async def safe_send_message(
    bot: Bot,
    user_id: int,
    text: str,
    reply_markup: Union[InlineKeyboardMarkup, None] = None,
    parse_mode: str = "HTML",
) -> None:
    """Безопасная отправка сообщения"""
    try:
        await bot.send_message(
            chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")


async def safe_edit_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: Union[InlineKeyboardMarkup, None] = None,
    parse_mode: str = "HTML",
) -> bool:
    """Безопасное редактирование сообщения. Возвращает True если успешно"""
    try:
        if (
            callback.message
            and hasattr(callback.message, "edit_text")
            and hasattr(callback.message, "message_id")
        ):  # InaccessibleMessage не имеет message_id
            await callback.message.edit_text(  # type: ignore
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            return True
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")

    # Если редактирование не удалось, отправляем новое сообщение
    if callback.from_user and callback.bot:
        await safe_send_message(
            callback.bot, callback.from_user.id, text, reply_markup, parse_mode
        )

    return False


@router.message(Command("addtopic"))
@check_and_add_user
@send_typing_action
async def start_add_topic(message: Message, state: FSMContext) -> None:
    """Начало процесса добавления новой темы"""
    if not message.from_user:
        logger.warning("Команда /addtopic получена без информации о пользователе")
        return

    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} начал добавление новой темы")

    await state.set_state(AddTopicForm.waiting_for_method)

    await message.answer(
        "📚 <b>Добавление новой темы в базу знаний</b>\n\n"
        "Выберите способ добавления контента:",
        reply_markup=get_input_method_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    F.data == "addtopic_manual", StateFilter(AddTopicForm.waiting_for_method)
)
@check_and_add_user
@send_typing_action
async def process_manual_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора ручного ввода"""
    await callback.answer()
    await state.set_state(AddTopicForm.waiting_for_title)

    await safe_edit_message(
        callback, "📝 <b>Ручной ввод темы</b>\n\nВведите заголовок для новой темы:"
    )

    if callback.from_user:
        logger.info(f"Пользователь {callback.from_user.id} выбрал ручной ввод темы")


@router.callback_query(
    F.data == "addtopic_file", StateFilter(AddTopicForm.waiting_for_method)
)
@check_and_add_user
@send_typing_action
async def process_file_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора загрузки файла"""
    await callback.answer()
    await state.set_state(AddTopicForm.waiting_for_file)

    await safe_edit_message(
        callback,
        "📄 <b>Загрузка файла</b>\n\n"
        "Отправьте файл с контентом (.txt, .pdf, .doc, .docx).\n"
        "Максимальный размер файла: 20 МБ",
    )

    if callback.from_user:
        logger.info(f"Пользователь {callback.from_user.id} выбрал загрузку файла")


@router.message(StateFilter(AddTopicForm.waiting_for_title), F.text)
@check_and_add_user
@send_typing_action
async def process_title_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода заголовка"""
    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    title = message.text.strip()

    if len(title) < 3:
        await message.answer(
            "❌ Заголовок слишком короткий. Минимум 3 символа.\nПопробуйте еще раз:"
        )
        return

    if len(title) > 200:
        await message.answer(
            "❌ Заголовок слишком длинный. Максимум 200 символов.\nПопробуйте еще раз:"
        )
        return

    await state.update_data(title=title, input_method="manual")
    await state.set_state(AddTopicForm.waiting_for_content)

    await message.answer(
        f"✅ Заголовок сохранен: <b>{title}</b>\n\nТеперь введите содержимое темы:",
        parse_mode="HTML",
    )

    logger.info(f"Пользователь {user_id} ввел заголовок: {title}")


@router.message(StateFilter(AddTopicForm.waiting_for_content), F.text)
@check_and_add_user
@send_typing_action
async def process_content_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода содержимого"""
    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    content = message.text.strip()

    if len(content) < 10:
        await message.answer(
            "❌ Содержимое слишком короткое. Минимум 10 символов.\nПопробуйте еще раз:"
        )
        return

    data = await state.get_data()
    title = data.get("title", "Без названия")

    await state.update_data(content=content)
    await state.set_state(AddTopicForm.waiting_for_confirmation)

    # Показываем превью
    preview = content[:200] + "..." if len(content) > 200 else content

    await message.answer(
        f"📋 <b>Предварительный просмотр:</b>\n\n"
        f"<b>Заголовок:</b> {title}\n"
        f"<b>Содержимое:</b> {preview}\n\n"
        f"<b>Общий размер:</b> {len(content)} символов\n\n"
        "Подтвердите загрузку в базу знаний:",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )

    logger.info(f"Пользователь {user_id} ввел содержимое ({len(content)} символов)")


@router.message(StateFilter(AddTopicForm.waiting_for_file), F.document)
@check_and_add_user
@send_typing_action
async def process_file_upload(message: Message, state: FSMContext) -> None:
    """Обработка загрузки файла с использованием process_document"""
    if not message.from_user or not message.document or not message.bot:
        return

    user_id = message.from_user.id
    document: Document = message.document

    # Проверка размера файла (20 МБ)
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer(
            "❌ Файл слишком большой. Максимальный размер: 20 МБ\n"
            "Попробуйте загрузить файл меньшего размера."
        )
        return

    allowed_extensions = {".txt", ".pdf", ".doc", ".docx"}
    file_name = document.file_name or "unknown"
    if not any(file_name.lower().endswith(ext) for ext in allowed_extensions):
        await message.answer(
            "❌ Неподдерживаемый тип файла.\n"
            "Поддерживаемые форматы: .txt, .pdf, .doc, .docx\n\n"
            "Попробуйте еще раз:"
        )
        return

    title = await process_document(
        bot=message.bot,
        file_id=document.file_id,
        file_name=file_name,
        user_id=user_id,
        message=message,
        state=state,
    )

    if title:
        await message.answer(
            f"📄 <b>Файл успешно обработан!</b>\n\n<b>Заголовок:</b> {title}",
            parse_mode="HTML",
            reply_markup=get_confirmation_keyboard(),
        )
        await state.update_data(title=title, input_method="file")
        await state.set_state(AddTopicForm.waiting_for_confirmation)


@router.callback_query(
    F.data == "addtopic_confirm", StateFilter(AddTopicForm.waiting_for_confirmation)
)
@check_and_add_user
@send_typing_action
async def confirm_upload(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение и загрузка контента"""
    if not callback.from_user:
        return

    user_id = callback.from_user.id

    try:
        await callback.answer("Загружаем данные в базу знаний...")

        data = await state.get_data()
        title = data.get("title", "Без названия")
        input_method = data.get("input_method", "manual")

        text = data.get("content", "")
        if not text:
            await safe_edit_message(callback, "❌ Ошибка: содержимое не найдено")
            return

        # Загружаем текстовый контент
        result = await loaddata_client.load_text_data(title, text, user_id)

        if result:
            await safe_edit_message(
                callback,
                f"✅ <b>Тема успешно добавлена!</b>\n\n"
                f"<b>Заголовок:</b> {title}\n"
                f"<b>Метод:</b> {'Ручной ввод' if input_method == 'manual' else 'Загрузка файла'}\n\n"
                "Тема добавлена в базу знаний и будет доступна для поиска.",
            )
            logger.info(f"Пользователь {user_id} успешно добавил тему: {title}")
        else:
            await safe_edit_message(
                callback,
                "❌ <b>Ошибка при загрузке</b>\n\n"
                "Не удалось добавить тему в базу знаний.\n"
                "Попробуйте еще раз или обратитесь к администратору.",
            )
            logger.error(f"Ошибка при загрузке темы от пользователя {user_id}")

    except Exception as e:
        logger.error(
            f"Ошибка при подтверждении загрузки от пользователя {user_id}: {e}"
        )
        await safe_edit_message(
            callback,
            "❌ Произошла ошибка при загрузке.\n"
            "Попробуйте еще раз или обратитесь к администратору.",
        )
    finally:
        await state.clear()


@router.callback_query(F.data == "addtopic_cancel", StateFilter("*"))
@check_and_add_user
@send_typing_action
async def cancel_add_topic(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена добавления темы"""
    try:
        await callback.answer("Операция отменена")
        await state.clear()

        await safe_edit_message(
            callback,
            "❌ <b>Добавление темы отменено</b>\n\n"
            "Для начала новой операции используйте команду /addtopic",
        )

        if callback.from_user:
            logger.info(f"Пользователь {callback.from_user.id} отменил добавление темы")

    except Exception as e:
        logger.error(f"Ошибка при отмене операции: {e}")


# Простая заглушка для других callback'ов
@router.callback_query(
    F.data == "addtopic_edit_title", StateFilter(AddTopicForm.waiting_for_confirmation)
)
@check_and_add_user
@send_typing_action
async def edit_title_stub(callback: CallbackQuery, state: FSMContext) -> None:
    """Заглушка для редактирования заголовка"""
    await callback.answer()
    data = await state.get_data()
    current_title = data.get("title", "")
    await state.set_state(AddTopicForm.waiting_for_title_edit)
    await safe_edit_message(
        callback,
        f"✏️ <b>Редактирование заголовка</b>\n\n"
        f"Текущий заголовок: <i>{current_title}</i>\n\n"
        "Введите новый заголовок:",
        parse_mode="HTML",
    )
    if callback.from_user:
        logger.info(
            f"Пользователь {callback.from_user.id} начал редактирование заголовка"
        )


# для обработки нового заголовка
@router.message(StateFilter(AddTopicForm.waiting_for_title_edit), F.text)
@check_and_add_user
@send_typing_action
async def process_title_edit(message: Message, state: FSMContext) -> None:
    """Обработка нового заголовка"""
    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    new_title = message.text.strip()

    if len(new_title) < 3:
        await message.answer(
            "❌ Заголовок слишком короткий. Минимум 3 символа.\nПопробуйте еще раз:"
        )
        return

    if len(new_title) > 200:
        await message.answer(
            "❌ Заголовок слишком длинный. Максимум 200 символов.\nПопробуйте еще раз:"
        )
        return

    await state.update_data(title=new_title)
    await state.set_state(AddTopicForm.waiting_for_confirmation)

    data = await state.get_data()
    content = data.get("content", "")
    preview = content[:200] + "..." if len(content) > 200 else content

    await message.answer(
        f"📋 <b>Обновленный предварительный просмотр:</b>\n\n"
        f"<b>Заголовок:</b> {new_title}\n"
        f"<b>Содержимое:</b> {preview}\n\n"
        f"<b>Общий размер:</b> {len(content)} символов\n\n"
        "Подтвердите загрузку в базу знаний:",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    logger.info(f"Пользователь {user_id} изменил заголовок на: {new_title}")
