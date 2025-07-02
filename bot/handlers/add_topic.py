from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter

from utils.decorators import check_and_add_user, send_typing_action
from utils.states import LoadDataForm
from utils.helpers import process_document

from config import loading_sticker

router = Router()

# Обработчик команды /addtopic
@router.message(Command("addtopic"))
@check_and_add_user
@send_typing_action
async def handle_load_data(message: Message, state: FSMContext):
    msg = await message.answer(
        "Выберите способ загрузки данных:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Загрузить файл", callback_data='load_file')],
                [InlineKeyboardButton(text="Ввести вручную", callback_data='manual_input')],
                [InlineKeyboardButton(text="Отмена", callback_data='cancel')]
            ]
        )
    )
    await state.set_data({'bot_message_id': msg.message_id})
    await state.set_state(LoadDataForm.waiting_for_choice)

# Обработчик случайной отправки файла
@router.message(F.content_type == "document", StateFilter(None))
@check_and_add_user
@send_typing_action
async def docs_message_handler(message: Message, state: FSMContext):
    msg = await message.answer(
        "Вы отправили файл. Хотите добавить новую тему?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Да", callback_data='yes_add_topic')],
                [InlineKeyboardButton(text="Нет", callback_data='no_cancel')]
            ]
        )
    )
    await state.set_data({
        'file_id': message.document.file_id,
        'file_name': message.document.file_name,
        'bot_message_id': msg.message_id,
        'original_message_id': message.message_id
    })
    await state.set_state(LoadDataForm.waiting_for_confirmation)

# Обработчик подтверждения "Да" для случайной отправки файла
@router.callback_query(F.data == "yes_add_topic", StateFilter(LoadDataForm.waiting_for_confirmation))
async def process_yes_add_topic(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        print(f"Failed to answer callback: {e}") 

    data = await state.get_data()
    file_id = data['file_id']
    file_name = data['file_name']
    bot_message_id = data['bot_message_id']
    original_message_id = data.get('original_message_id')

    # Обрабатываем файл
    response, title = await process_document(
        bot=callback.bot,
        file_id=file_id,
        file_name=file_name,
        user_id=callback.from_user.id,
        message=callback.message,
        state=state
    )

    if response:
        if original_message_id:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=original_message_id)
        await callback.message.edit_text(f"Данные успешно загружены из файла! ({title})")
    elif title:
        await callback.message.edit_text(f"Ошибка при загрузке данных из файла {title}.")

# Обработчик отказа "Нет"
@router.callback_query(F.data == "no_cancel", StateFilter(LoadDataForm.waiting_for_confirmation))
async def process_no_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Действие отменено.")
    await state.clear()

# Обработчик выбора "Загрузить файл" после /addtopic
@router.callback_query(F.data == "load_file", StateFilter(LoadDataForm.waiting_for_choice))
async def process_load_file_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Пожалуйста, отправьте файл (.txt, .docx или .pdf).",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]]
        )
    )
    await state.set_state(LoadDataForm.waiting_for_file)

# Обработчик получения файла после выбора "Загрузить файл"
@router.message(StateFilter(LoadDataForm.waiting_for_file), F.content_type == "document")
@check_and_add_user
@send_typing_action
async def process_file(message: Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data['bot_message_id']

    response, title = await process_document(
        bot=message.bot,
        file_id=message.document.file_id,
        file_name=message.document.file_name,
        user_id=message.from_user.id,
        message=message,
        state=state
    )

    if response:
        await message.delete()
        await message.bot.edit_message_text(
            f"Данные успешно загружены из файла! ({title})",
            chat_id=message.chat.id,
            message_id=bot_message_id
        )
    elif title:
        await message.delete()
        await message.bot.edit_message_text(
            f"Ошибка при загрузке данных из файла {title}.",
            chat_id=message.chat.id,
            message_id=bot_message_id
        )

# Обработчик выбора "Ввести вручную"
@router.callback_query(F.data == "manual_input", StateFilter(LoadDataForm.waiting_for_choice))
async def process_manual_input_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer() 
    await callback.message.edit_text(
        "Пожалуйста, введите заголовок для новой темы:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]]
        )
    )
    await state.set_state(LoadDataForm.waiting_for_title)

# Обработчик ввода заголовка
@router.message(StateFilter(LoadDataForm.waiting_for_title))
@check_and_add_user
@send_typing_action
async def process_title(message: Message, state: FSMContext):
    title = message.text
    await state.update_data(title=title)
    await message.delete()

    data = await state.get_data()
    bot_message_id = data['bot_message_id']

    await message.bot.edit_message_text(
        f'Заголовок - "{title}"\nТеперь введите текст:',
        chat_id=message.chat.id,
        message_id=bot_message_id,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]]
        )
    )
    await state.set_state(LoadDataForm.waiting_for_text)

# Обработчик ввода текста
@router.message(StateFilter(LoadDataForm.waiting_for_text))
@check_and_add_user
@send_typing_action
async def process_text(message: Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    title = data['title']
    bot_message_id = data['bot_message_id']

    msg = await message.answer('Секунду, мне нужно время, чтобы запомнить...')
    loading_message = await message.answer_sticker(loading_sticker)
    response = add_new_topic(title, text, message.from_user.id)

    await msg.delete()
    await loading_message.delete()

    if response:
        await message.delete()
        await message.bot.edit_message_text(
            f"Данные успешно загружены! ({title})",
            chat_id=message.chat.id,
            message_id=bot_message_id
        )
    else:
        await message.delete()
        await message.bot.edit_message_text(
            f"Ошибка при загрузке данных: {title}.",
            chat_id=message.chat.id,
            message_id=bot_message_id
        )
    await state.clear()

# Обработчик отмены
@router.callback_query(F.data == "cancel", StateFilter("*"))
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer() 
    await callback.message.edit_text("Действие отменено.")
    await state.clear()