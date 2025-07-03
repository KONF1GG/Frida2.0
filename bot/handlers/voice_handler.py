"""
Обработчик голосовых сообщений и аудио файлов.
Обеспечивает транскрипцию через Whisper API и последующую обработку текста.
"""

import logging
import aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ContentType

from utils.decorators import check_and_add_user, send_typing_action
from utils.helpers import check_transcription_status
from config import bot_config

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(
    lambda message: message.content_type in [ContentType.VOICE, ContentType.AUDIO]
)
@check_and_add_user
@send_typing_action
async def handle_audio_or_voice(message: Message):
    """Обработка голосовых сообщений и аудио файлов."""
    if not message.from_user or not message.bot:
        logger.warning("Получено голосовое сообщение без пользователя или бота")
        return

    user_id = message.from_user.id
    file = message.voice if message.voice else message.audio

    if not file:
        logger.warning(f"Не удалось получить аудио файл от пользователя {user_id}")
        await message.answer("❌ Ошибка: Не удалось обработать аудио сообщение")
        return

    file_id = file.file_id

    try:
        file_info = await message.bot.get_file(file_id)
        if not file_info.file_path:
            logger.error(
                f"Не удалось получить путь к аудио файлу для пользователя {user_id}"
            )
            await message.answer("❌ Ошибка: Не удалось получить аудио файл")
            return

        file_path = file_info.file_path

    except Exception as e:
        logger.error(
            f"Ошибка при получении информации об аудио файле для пользователя {user_id}: {e}"
        )
        await message.answer("❌ Ошибка при получении аудио файла")
        return

    loading_message = await message.answer_sticker(bot_config.loading_sticker)

    async with aiohttp.ClientSession() as session:
        try:
            # Получаем файл с серверов Telegram
            file_url = (
                f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"
            )

            async with session.get(file_url) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    form_data = aiohttp.FormData()
                    form_data.add_field(
                        "file",
                        audio_data,
                        filename="audio.ogg",
                        content_type="audio/ogg",
                    )

                    # Отправка файла на API Whisper
                    async with session.post(
                        f"{bot_config.whisper_api}/transcribe/", data=form_data
                    ) as api_response:
                        if api_response.status == 200:
                            result = await api_response.json()
                            task_id = result.get("task_id")

                            if task_id:
                                logger.info(
                                    f"Запущена транскрипция для пользователя {user_id}, task_id: {task_id}"
                                )
                                # Запуск проверки статуса транскрипции
                                await check_transcription_status(
                                    task_id, message, session
                                )
                            else:
                                logger.error(
                                    f"Не получен task_id для пользователя {user_id}"
                                )
                                await message.answer(
                                    "❌ Ошибка при инициализации транскрипции"
                                )
                        else:
                            error_text = await api_response.text()
                            logger.error(
                                f"Ошибка Whisper API для пользователя {user_id}: {error_text}"
                            )
                            await message.answer(
                                "❌ Ошибка при отправке файла на транскрипцию. Попробуйте позже."
                            )
                else:
                    logger.error(
                        f"Ошибка при загрузке файла с Telegram для пользователя {user_id}: {response.status}"
                    )
                    await message.answer("❌ Ошибка при загрузке аудио файла")

        except Exception as e:
            logger.exception(
                f"Ошибка при обработке аудио для пользователя {user_id}: {e}"
            )
            await message.answer(
                "❌ Произошла ошибка при обработке вашего аудио сообщения."
            )

        finally:
            try:
                await loading_message.delete()
            except Exception as delete_error:
                logger.warning(f"Не удалось удалить loading message: {delete_error}")
