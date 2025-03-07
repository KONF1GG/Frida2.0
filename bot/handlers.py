import asyncio
from io import StringIO
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.enums.chat_action import ChatAction
from aiogram.enums import ParseMode
import config
from databases import Milvus
# from funcs import transcribe_audio
from .utils import check_and_add_user, send_typing_action
from crud import PostgreSQL, add_new_topic, insert_all_data_from_postgres_to_milvus, insert_wiki_data
from config import WHISPER_API, postgres_config
from mistral import mistral
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, ContentType
from config import loading_sticker
import aiohttp

import pandas as pd
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
    msg = await message.answer("Пожалуйста, введите заголовок для новой темы, которую я запомню:",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data='cancel')]]))
    
    await state.set_data({'user_title_message_id': message.message_id, 'bot_title_message_id': msg.message_id})
    await state.set_state(TopicForm.waiting_for_title)


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
    loading_message = await message.answer_sticker(loading_sticker)
    responese = add_new_topic(title, text, message.from_user.id)

    await msg.delete()
    await loading_message.delete()
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
        # await message.answer("Выгружаю данные... Пожалуйста, подождите")
        loading_message = await message.answer_sticker(loading_sticker)
        response = insert_wiki_data()
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        milvus_data_count, deleted_data_count = insert_all_data_from_postgres_to_milvus()
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        if response:
            if deleted_data_count:
                await loading_message.delete()
                await message.answer(f'Было обнаружено и удалено {deleted_data_count} дубликатов. Сейчас в базе {milvus_data_count} записей')
            else:
                await loading_message.delete()
                await message.answer(f'Сейчас в базе {milvus_data_count} записей')
        else:
            await loading_message.delete()
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
    

@router.message(lambda message: message.document and message.document.mime_type in ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'])
@check_and_add_user
@send_typing_action
async def handle_file(message: Message):
    file = message.document
    loading_message = await message.answer_sticker(loading_sticker)

    try:
        file_info = await message.bot.get_file(file.file_id)
        file_path = await message.bot.download_file(file_info.file_path)

        file_data = file_path.getvalue()
    except Exception as e:
        await message.answer("Не удалось загрузить файл. Пожалуйста, попробуйте снова.")
        return

    try:
        if file.mime_type == 'text/csv':
            try:
                try:
                    data = pd.read_csv(StringIO(file_data.decode('utf-8')), delimiter=';')
                except UnicodeDecodeError:
                    data = pd.read_csv(StringIO(file_data.decode('windows-1251', errors='replace')), delimiter=';')
                except Exception as e:
                        data = pd.read_csv(StringIO(file_data.decode('utf-8')), delimiter=',')
            except Exception as e:
                await message.answer(f"Ошибка при чтении CSV файла: {str(e)}. Пожалуйста, убедитесь, что файл в формате CSV имеет кодировку UTF-8 или windows-1251, а также желательно использовать разделитель - ';'")
                return

        elif file.mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            try:
                try:
                    data = pd.read_excel(file_path)
                except Exception as e:
                    await message.answer(f"Ошибка при чтении Excel файла: {str(e)}. Убедитесь, что файл в формате Excel (.xlsx или .xls) и поддерживается.")
                    return
            except Exception as e:
                await message.answer(f"Ошибка при чтении Excel файла: {str(e)}. Попробуйте загрузить другой файл.")
                return

        else:
            await message.answer("Неподдерживаемый тип файла. Пожалуйста, загрузите файл в формате CSV или Excel.")
            return

        try:
            csv_buffer = StringIO()
            data.to_csv(csv_buffer, index=False)
            csv_text = csv_buffer.getvalue()
        except Exception as e:
            await message.answer(f"Ошибка при конвертации данных в CSV: {str(e)}. Попробуйте еще раз.")
            return

        query = message.caption if message.caption else "Напиши общий отчет по таблице"
        try:
            message.answer(query)
            mistral_response = await mistral(query, context=csv_text,  input_type='csv')
            if mistral_response:
                await message.answer(mistral_response)
            else:
                await message.answer("Произошла ошибка при обработке файла в Mistral.")
        except Exception as e:
            await message.answer(f"Произошла ошибка при отправке запроса в Mistral: {str(e)}. Попробуйте позже.")

    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке файла: {str(e)}. Пожалуйста, попробуйте снова.")
    finally:
        await loading_message.delete()


async def search_milvus(text, user_id, postgres_db: PostgreSQL):
    milvus_db = Milvus(config.MILVUS_HOST, config.MILVUS_PORT, 'Frida_bot_data')
    milvus_response = milvus_db.search(text)
    milvus_db.connection_close()
    hashs = []
    for result in milvus_response:
        for item in result:
            hash_value = item.id
            distance_value = item.distance 
            hashs.append(hash_value)        
        print(f"ID: {hash_value}, Distance: {distance_value}")

    contexts = postgres_db.get_items_by_hashs(tuple(hashs), user_id=user_id)
    result_string = "Последние 3 сообщения:\n"
    message_hostory = postgres_db.get_history(user_id)
    for i, msg in enumerate(message_hostory, 1):
        query = msg[2]
        response = msg[3]

        result_string += f"{i}) Зпрос пользователя: {query}\nТвой ответ: {response}\n"
    combined_context = ""

    for i, (book_name, text, url) in enumerate(contexts, start=1):
        book_name = book_name if book_name else ''
        combined_context += f"Контекст {i}:\n{book_name+'\n'+text}\nURL: {url}\n"
    return {'combined_context': combined_context, 'result_string': result_string, 'hashs': hashs}

@router.message(lambda message: message.content_type in [ContentType.VOICE, ContentType.AUDIO])
async def handle_audio_or_voice(message: Message):
    """Обработка голосовых сообщений и аудио файлов."""
    postgres = PostgreSQL(**config.postgres_config)
    file = message.voice if message.voice else message.audio
    if not file:
        await message.answer('Ошибка: Не удалось обработать аудио сообщение')
        return

    file_id = file.file_id
    file_info = await message.bot.get_file(file_id)
    file_path = file_info.file_path

    async with aiohttp.ClientSession() as session:
        loading_message = await message.answer_sticker(loading_sticker)
        try:
            # Получаем файл с серверов Telegram
            file_url = f'https://api.telegram.org/file/bot{message.bot.token}/{file_path}'
            async with session.get(file_url) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    form_data = aiohttp.FormData()
                    form_data.add_field('file', audio_data, filename='audio.ogg', content_type='audio/ogg')

                    # Отправка файла на API Whisper
                    async with session.post(f'{WHISPER_API}/transcribe/', data=form_data) as api_response:
                        if api_response.status == 200:
                            result = await api_response.json()
                            task_id = result.get('task_id')

                            # Запуск проверки статуса транскрипции
                            await check_transcription_status(task_id, message, session)

                        else:
                            
                            await message.answer('Ошибка при отправке файла на транскрипцию. Попробуйте позже.')
        except Exception as e:
            print(f"Ошибка при обработке аудио: {e}")
            await message.answer('Произошла ошибка при обработке вашего аудио сообщения.')
        finally:
            await loading_message.delete()



async def check_transcription_status(task_id: str, message: Message, session: aiohttp.ClientSession):
    """Проверка статуса транскрипции каждые 5 секунд, до 5 попыток."""
    await asyncio.sleep(2)
    retries = 5
    delay = 5  
    
    for attempt in range(1, retries + 1):
        try:
            # Получаем статус транскрипции
            async with session.get(f'{WHISPER_API}/transcribe/status/{task_id}') as response:
                if response.status == 200:
                    status = await response.json()
                    if status.get('status') == 'completed':
                        await fetch_transcription_result(task_id, message, session)
                        return
                    else:
                        await asyncio.sleep(delay)  # Ждем перед новой попыткой
                else:
                    await message.answer("Не удалось получить статус транскрипции.")
        except Exception as e:
            await message.answer(f"Произошла ошибка при получении статуса транскрипции. Попробуйте позже.")
            return

    await message.answer("Транскрипция не была завершена. Попробуйте снова позже.")


async def fetch_transcription_result(task_id: str, message: Message, session: aiohttp.ClientSession):
    """Получаем результат транскрипции."""
    try:
        postgres_db = PostgreSQL(**config.postgres_config)
        async with session.get(f'{WHISPER_API}/transcribe/result/{task_id}') as response:
            if response.status == 200:
                transcription = await response.json()
                
                if 'result' in transcription and 'segments' in transcription['result']:
                    segments = transcription['result']['segments']
                    
                    transcription_text = "\n".join([segment['text'] for segment in segments])

                    if transcription_text:
                        if not message.caption:
                            query = transcription_text
                            try:

                                result = await search_milvus(query, message.from_user.id, postgres_db)

                                mistral_response = await mistral(query, result.get('combined_context'), result.get('result_string'))
                                
                                if mistral_response:
                                    await message.answer(f'{mistral_response}', parse_mode=ParseMode.HTML)
                                    postgres_db.log_message(message.from_user.id,'Расшифрованное голосовое: ' + transcription_text, mistral_response, result.get('hashs'))
                                else:
                                    await message.answer('Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
                            
                            except Exception as e:
                                await message.answer(f"Произошла ошибка: {str(e)}", parse_mode=ParseMode.HTML)
                        else:
                            result_string = ''
                            message_hostory = postgres_db.get_history(message.from_user.id)
                            for i, msg in enumerate(message_hostory, 1):
                                query = msg[2]
                                response = msg[3]

                                result_string += f"{i}) Зпрос пользователя: {query}\nТвой ответ: {response}\n"
                            mistral_response = await mistral(message.caption, context=transcription_text, history=result_string)

                            if mistral_response:
                                await message.answer(f'{mistral_response}', parse_mode=ParseMode.HTML)
                                postgres_db.log_message(message.from_user.id, message.caption + 'Расшифрованное голосовое: ' + transcription_text , mistral_response, '')
                            else:
                                await message.answer('Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
                    else:
                        await message.answer("Не удалось получить текст транскрипции. Пожалуйста, попробуйте позже.")
                else:
                    await message.answer("Не удалось найти транскрипцию в ответе от сервера.")
            else:
                await message.answer("Не удалось получить результат транскрипции.")
    except Exception as e:
        print(f"Ошибка при получении результата транскрипции: {e}")
        await message.answer("Ошибка при получении результата транскрипции.")
    finally:
        postgres_db.connection_close()


@router.message()
@check_and_add_user
@send_typing_action
async def message_handler(message: Message):
    """Обработка обычных сообщений."""
    postgres_db = PostgreSQL(**config.postgres_config)
    result = await search_milvus(message.text, message.from_user.id, postgres_db)
    loading_message = await message.answer_sticker(loading_sticker)

    try:
        mistral_response = await mistral(message.text, result.get('combined_context'), result.get('result_string'))
        
        if mistral_response:
            await message.answer(f'{mistral_response}', parse_mode=ParseMode.HTML)
            postgres_db.log_message(message.from_user.id, message.text, mistral_response, result.get('hashs'))
        else:
            await message.answer('Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
    
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", parse_mode=ParseMode.HTML)

    finally:
        await loading_message.delete()
