import asyncio
from logging import config
import os
import PyPDF2
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import aiohttp
import docx
from aiogram.enums import ParseMode
from config import WHISPER_API, loading_sticker
from database.postgres import PostgreSQL

async def process_document(bot, file_id: str, file_name: str, user_id: int, message: Message, state: FSMContext):
    title = os.path.splitext(file_name)[0]
    file = await bot.get_file(file_id)
    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)

    text = ""
    try:
        if file_name.endswith('.txt'):
            text = downloaded_file.read().decode('utf-8')
        elif file_name.endswith('.docx'):
            doc = docx.Document(downloaded_file)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif file_name.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(downloaded_file)
            text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        else:
            await message.answer("Формат файла не поддерживается. Используйте .txt, .docx или .pdf.")
            await state.clear()
            return False, None
    except Exception as e:
        await message.answer(f"Ошибка при чтении файла: {e}")
        await state.clear()
        return False, None

    msg = await message.answer('Секунду, мне нужно время, чтобы запомнить...')
    loading_message = await message.answer_sticker(loading_sticker)
    response = add_new_topic(title, text, user_id)
    await msg.delete()
    await loading_message.delete()

    return response, title


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
                                    postgres_db.log_message(message.from_user.id,'Расшифрованное голосовое: ' + transcription_text, mistral_response, True, result.get('hashs'))
                                else:
                                    err_mes = 'Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...'
                                    await message.answer(err_mes, parse_mode=ParseMode.HTML)
                                    postgres_db.log_message(message.from_user.id,'Расшифрованное голосовое: ' + transcription_text, err_mes, False, result.get('hashs'))

                            except RuntimeError as e:
                                postgres_db.log_message(message.from_user.id,'Расшифрованное голосовое: ' + transcription_text, 'gpu timeout: ' + str(e), False, result.get('hashs'))
                                await message.answer(f"Произошла ошибка: {str(e)}", parse_mode=ParseMode.HTML)
                            except Exception as e:
                                postgres_db.log_message(message.from_user.id,'Расшифрованное голосовое: ' + transcription_text, str(e), False, result.get('hashs'))
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
                                postgres_db.log_message(message.from_user.id, message.caption + 'Расшифрованное голосовое: ' + transcription_text , mistral_response, True, '')
                            else:
                                postgres_db.log_message(message.from_user.id, message.caption + 'Расшифрованное голосовое: ' + transcription_text , 'Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', False, '')
                                await message.answer('Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
                    else:
                        postgres_db.log_message(message.from_user.id, message.caption, 'Не удалось получить текст транскрипции. Пожалуйста, попробуйте позже.', False, '')
                        await message.answer("Не удалось получить текст транскрипции. Пожалуйста, попробуйте позже.")
                else:
                    postgres_db.log_message(message.from_user.id, message.caption , 'Не удалось найти транскрипцию в ответе от сервера.', False, '')
                    await message.answer("Не удалось найти транскрипцию в ответе от сервера.")
            else:
                postgres_db.log_message(message.from_user.id, message.caption , 'Не удалось получить результат транскрипции.', False, '')
                await message.answer("Не удалось получить результат транскрипции.")
    except Exception as e:
        postgres_db.log_message(message.from_user.id, message.caption , str(e), False, '')
        print(f"Ошибка при получении результата транскрипции: {e}")
        await message.answer("Ошибка при получении результата транскрипции.")
    finally:
        postgres_db.connection_close()

