import ast
from email.errors import MessageError
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.enums.chat_action import ChatAction
from aiogram.enums import ParseMode
from regex import R
import config
from databases import Milvus
from .utils import check_and_add_user, send_typing_action
from crud import PostgreSQL, add_new_topic, insert_all_data_from_postgres_to_milvus, insert_wiki_data
from config import postgres_config
from mistral import mistral
from aiogram.fsm.context import FSMContext
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery

router = Router()

@router.message(CommandStart())
@check_and_add_user
@send_typing_action
async def command_start_handler(message: Message):
    await message.answer(f"Привет, {message.from_user.full_name}!")

# @router.message(Command("remove_keyboard"))
# async def remove_keyboard(message: Message):
#     await message.answer(
#         "Клавиатура удалена.",
#         reply_markup=ReplyKeyboardRemove()
#     )

class TopicForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_text = State()

# Обработчик нажатия кнопки "Отмена" на любой стадии
@router.callback_query(lambda c: c.data in ('cancel'))
@check_and_add_user
async def cancel_add_topic(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if 'bot_title_message_id' in data:
        try:
            await callback_query.bot.delete_message(callback_query.message.chat.id, data['bot_title_message_id'])
        except Exception as e:
            print(f"Ошибка при удалении сообщения заголовка: {e}")
    if 'user_title_message_id' in data:
        try:
            await callback_query.bot.delete_message(callback_query.message.chat.id, data['user_title_message_id'])
        except Exception as e:
            print(f"Ошибка при удалении сообщения текста: {e}")

    # Очищаем состояние
    await state.clear()


# Обработчик команды /addtopic
@router.message(Command("addtopic"))
@check_and_add_user
@send_typing_action
async def handle_add_topic(message: Message, state: FSMContext):
    # Отправляем запрос на заголовок с кнопкой "Отмена"
    msg = await message.answer("Пожалуйста, введите заголовок для новой темы, которую я запомню:",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]]))
    
    await state.set_data({'user_title_message_id': message.message_id, 'bot_title_message_id': msg.message_id})
    # Устанавливаем состояние
    await state.set_state(TopicForm.waiting_for_title)


# Обработчик для ввода заголовка
@router.message(TopicForm.waiting_for_title)
@check_and_add_user
@send_typing_action
async def process_title(message: Message, state: FSMContext):
    title = message.text
    await state.update_data(title=title)

    user_message_id = message.message_id
    try:
        await message.bot.delete_message(message.chat.id, user_message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")
    
    data = await state.get_data()
    bot_title_message_id = data['bot_title_message_id']
    await message.bot.edit_message_text(
        f'Заголовок - "{title}"\nТеперь введите текст:',
        chat_id=message.chat.id,
        message_id=bot_title_message_id,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]])
    )

    await state.set_state(TopicForm.waiting_for_text)



# Обработчик для ввода текста
@router.message(TopicForm.waiting_for_text)
@check_and_add_user
@send_typing_action
async def process_text(message: Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    title = data['title']

    msg = await message.answer('Секунду, мне нужно время, чтобы запомнить...')
    
    # Добавляем новый топик в базу данных
    responese = add_new_topic(title, text, message.from_user.id)

    await msg.delete()
    # Редактируем сообщение, где просили ввести текст
    bot_text_message_id = data['bot_title_message_id']
    if responese:
        await message.delete()
        await message.bot.edit_message_text(
            f"Данные успешно загружены! ({title})",
            chat_id=message.chat.id,
            message_id=bot_text_message_id
        )
    else:
        await message.delete()
        await message.bot.edit_message_text(
            f"Ошибка! {str(responese)}",
            chat_id=message.chat.id,
            message_id=bot_text_message_id
        )

    await state.clear()


@router.message(Command("loaddata"))
@check_and_add_user
@send_typing_action
async def handle_loaddata_command(message: Message):
    postgres = PostgreSQL(**postgres_config)
    isAdmin = postgres.check_user_is_admin(message.from_user.id)
    
    if isAdmin:
        await message.answer("Выгружаю данные... Пожалуйста, подождите")
        response = insert_wiki_data()
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        milvus_data_count, deleted_data_count = insert_all_data_from_postgres_to_milvus()
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        if response:
            if deleted_data_count:
                await message.answer(f'Было обнаружено и удалено {deleted_data_count} дубликатов. Сейчас в базе {milvus_data_count} записей')
            else:
                await message.answer(f'Сейчас в базе {milvus_data_count} записей')
        else:
            await message.answer('Произошла ошибка при попытке выгрузить данные из базы данных wiki')
    else:
        admins = postgres.get_admins()
        postgres.connection_close()
        
        keyboard = []
        
        for admin_id, admin_name in admins:
            button = [InlineKeyboardButton(text=admin_name, url=f'tg://user?id={admin_id}')]
            keyboard.append(button) 

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            'Прошу прощения, но у Вас нет прав на выполнение данной команды.\n'
            'Вот список пользователей, у которых они есть:',
            reply_markup=keyboard
        )
    


@router.message()
@check_and_add_user
@send_typing_action
async def message_handler(message: Message):
    """Обработка обычных сообщений."""
    milvus_db = Milvus(config.MILVUS_HOST, config.MILVUS_PORT, 'Frida_bot_data')
    postgres_db = PostgreSQL(**config.postgres_config)  
    milvus_response = milvus_db.search(message.text)
    milvus_db.connection_close()
    hashs = []
    for result in milvus_response:
        for item in result:
            hash_value = item.id
            distance_value = item.distance 
            hashs.append(hash_value)        
        print(f"ID: {hash_value}, Distance: {distance_value}")

    contexts = postgres_db.get_items_by_hashs(tuple(hashs), user_id=message.from_user.id)
    result_string = "Последние 3 сообщения:\n"
    message_hostory = postgres_db.get_history(message.from_user.id)
    for i, msg in enumerate(message_hostory, 1):
        query = msg[2]
        response = msg[3]

        result_string += f"{i}) Зпрос пользователя: {query}\nТвой ответ: {response}\n"
    combined_context = ""

    for i, (book_name, text, url) in enumerate(contexts, start=1):
        book_name = book_name if book_name else ''
        combined_context += f"Контекст {i}:\n{book_name+'\n'+text}\nURL: {url}\n"

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    mistral_response = await mistral(message.text, combined_context, result_string)
    if mistral:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        postgres_db.log_message(message.from_user.id, message.text, mistral_response, hashs)
        await message.answer(f'{mistral_response}', parse_mode=ParseMode.HTML)
    else:
        await message.answer('Прошу пощения, я не смогла обработать Ваш запрос. Попробуйте позже...')
