from aiogram import Router, F
from aiogram.types import Message

from utils.decorators import check_and_add_user, send_typing_action

from config import loading_sticker


router = Router()

@router.message(lambda message: message.content_type in [ContentType.VOICE, ContentType.AUDIO])
@check_and_add_user
@send_typing_action
async def handle_audio_or_voice(message: Message):
    """Обработка голосовых сообщений и аудио файлов."""
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
            postgres_db = PostgreSQL(**postgres_config)
            postgres_db.log_message(message.from_user.id, message.text, str(e), False, [''])
            postgres_db.connection_close()
            await message.answer('Произошла ошибка при обработке вашего аудио сообщения.')
        finally:
            await loading_message.delete()
