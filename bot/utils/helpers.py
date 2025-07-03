"""
Вспомогательные функции для обработки документов и голосовых сообщений.
"""

import asyncio
import logging
import os
import PyPDF2
import aiohttp
import docx
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import bot_config
from api.milvus import search_milvus
from bot.api.ai import call_ai
from api.log import log
from utils.user_settings import user_model

logger = logging.getLogger(__name__)


async def process_document(
    bot, file_id: str, file_name: str, user_id: int, message: Message, state: FSMContext
):
    """
    Обработка документов (txt, docx, pdf)

    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        file_name: Имя файла
        user_id: ID пользователя
        message: Сообщение пользователя
        state: Состояние FSM

    Returns:
        Tuple[bool, str]: (успех, заголовок)
    """
    title = os.path.splitext(file_name)[0]

    try:
        file = await bot.get_file(file_id)
        if not file.file_path:
            logger.error(f"Не удалось получить путь к файлу для пользователя {user_id}")
            await message.answer("❌ Ошибка при получении файла")
            await state.clear()
            return False, None

        downloaded_file = await bot.download_file(file.file_path)
        if not downloaded_file:
            logger.error(f"Не удалось скачать файл для пользователя {user_id}")
            await message.answer("❌ Ошибка при скачивании файла")
            await state.clear()
            return False, None


        text = ""
        try:
            if file_name.endswith(".txt"):
                text = downloaded_file.read().decode("utf-8")
            elif file_name.endswith(".docx"):
                doc = docx.Document(downloaded_file)
                text = "\n".join([para.text for para in doc.paragraphs])
            elif file_name.endswith(".pdf"):
                pdf_reader = PyPDF2.PdfReader(downloaded_file)
                text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
            else:
                await message.answer(
                    "❌ Формат файла не поддерживается. Используйте .txt, .docx или .pdf."
                )
                await state.clear()
                return False, None

        except Exception as e:
            logger.error(f"Ошибка при чтении файла для пользователя {user_id}: {e}")
            await message.answer(f"❌ Ошибка при чтении файла: {e}")
            await state.clear()
            return False, None

        if not text.strip():
            logger.warning(f"Пустой текст в файле для пользователя {user_id}")
            await message.answer("⚠️ Файл пуст или не содержит читаемого текста")
            await state.clear()
            return False, None

        await state.update_data(content=text)

        logger.info(f"Документ '{title}' успешно обработан для пользователя {user_id}")
        return title

    except Exception as e:
        logger.exception(
            f"Неожиданная ошибка при обработке документа для пользователя {user_id}: {e}"
        )
        await message.answer("❌ Произошла ошибка при обработке документа")
        await state.clear()
        return False, None


async def check_transcription_status(
    task_id: str, message: Message, session: aiohttp.ClientSession
):
    """
    Проверка статуса транскрипции каждые 5 секунд, до 5 попыток

    Args:
        task_id: ID задачи транскрипции
        message: Сообщение пользователя
        session: HTTP сессия
    """
    if not message.from_user:
        logger.warning("Проверка транскрипции без информации о пользователе")
        return

    user_id = message.from_user.id
    await asyncio.sleep(2)
    retries = 5
    delay = 5

    for attempt in range(1, retries + 1):
        try:
            # Получаем статус транскрипции
            async with session.get(
                f"{bot_config.whisper_api}/transcribe/status/{task_id}"
            ) as response:
                if response.status == 200:
                    status = await response.json()
                    if status.get("status") == "completed":
                        logger.info(
                            f"Транскрипция завершена для пользователя {user_id}, task_id: {task_id}"
                        )
                        await fetch_transcription_result(task_id, message, session)
                        return
                    else:
                        logger.debug(
                            f"Транскрипция в процессе для пользователя {user_id}, попытка {attempt}"
                        )
                        await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Ошибка получения статуса транскрипции для пользователя {user_id}: {response.status}"
                    )
                    await message.answer("❌ Не удалось получить статус транскрипции.")
                    return

        except Exception as e:
            logger.exception(
                f"Ошибка при проверке статуса транскрипции для пользователя {user_id}: {e}"
            )
            await message.answer(
                "❌ Произошла ошибка при получении статуса транскрипции. Попробуйте позже."
            )
            return

    logger.warning(
        f"Транскрипция не завершена за отведенное время для пользователя {user_id}"
    )
    await message.answer("⏰ Транскрипция не была завершена. Попробуйте снова позже.")


async def fetch_transcription_result(
    task_id: str, message: Message, session: aiohttp.ClientSession
):
    """
    Получение результата транскрипции и его обработка

    Args:
        task_id: ID задачи транскрипции
        message: Сообщение пользователя
        session: HTTP сессия
    """
    if not message.from_user:
        logger.warning(
            "Получение результата транскрипции без информации о пользователе"
        )
        return

    user_id = message.from_user.id

    try:
        async with session.get(
            f"{bot_config.whisper_api}/transcribe/result/{task_id}"
        ) as response:
            if response.status == 200:
                transcription = await response.json()

                if "result" in transcription and "segments" in transcription["result"]:
                    segments = transcription["result"]["segments"]
                    transcription_text = "\n".join(
                        [segment["text"] for segment in segments]
                    )

                    if transcription_text:
                        if not message.caption:
                            # Обычный запрос без дополнительного контекста
                            query = transcription_text

                            try:
                                result = await search_milvus(user_id, message)

                                if result:
                                    ai_response = await call_ai(
                                        query,
                                        result.get("combined_context", ""),
                                        result.get("chat_history", ""),
                                        model=user_model.get(user_id, "mistral-large-latest"),

                                    )

                                    if ai_response:
                                        await message.answer(
                                            ai_response, parse_mode=ParseMode.HTML
                                        )
                                        await log(
                                            user_id=user_id,
                                            query="Расшифрованное голосовое: "
                                            + transcription_text,
                                            ai_response=ai_response,
                                            status=1,
                                            hashes=result.get("hashs", []),
                                        )
                                        logger.info(
                                            f"Успешно обработано голосовое сообщение пользователя {user_id}"
                                        )
                                    else:
                                        err_mes = "⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже..."
                                        await message.answer(
                                            err_mes, parse_mode=ParseMode.HTML
                                        )
                                        await log(
                                            user_id=user_id,
                                            query="Расшифрованное голосовое: "
                                            + transcription_text,
                                            ai_response=err_mes,
                                            status=0,
                                            hashes=result.get("hashs", []),
                                        )
                                else:
                                    await message.answer(
                                        "❌ Ошибка при поиске контекста",
                                        parse_mode=ParseMode.HTML,
                                    )

                            except Exception as e:
                                logger.exception(
                                    f"Ошибка при обработке транскрипции для пользователя {user_id}: {e}"
                                )
                                await log(
                                    user_id=user_id,
                                    query="Расшифрованное голосовое: "
                                    + transcription_text,
                                    ai_response=str(e),
                                    status=0,
                                    hashes=[],
                                )
                                await message.answer(
                                    "❌ Произошла ошибка при обработке запроса",
                                    parse_mode=ParseMode.HTML,
                                )
                        else:
                            # Запрос с дополнительным контекстом из caption
                            ai_response = await call_ai(
                                message.caption,
                                combined_context=transcription_text,
                                chat_history="",
                                model=user_model.get(user_id, "mistral-large-latest"),
                            )

                            if ai_response:
                                await message.answer(
                                    ai_response, parse_mode=ParseMode.HTML
                                )
                                await log(
                                    user_id=user_id,
                                    query=message.caption
                                    + " Расшифрованное голосовое: "
                                    + transcription_text,
                                    ai_response=ai_response,
                                    status=1,
                                    hashes=[],
                                )
                            else:
                                err_msg = "⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже..."
                                await log(
                                    user_id=user_id,
                                    query=message.caption
                                    + " Расшифрованное голосовое: "
                                    + transcription_text,
                                    ai_response=err_msg,
                                    status=0,
                                    hashes=[],
                                )
                                await message.answer(err_msg, parse_mode=ParseMode.HTML)
                    else:
                        logger.warning(
                            f"Пустая транскрипция для пользователя {user_id}"
                        )
                        await log(
                            user_id=user_id,
                            query=message.caption or "",
                            ai_response="Не удалось получить текст транскрипции",
                            status=0,
                            hashes=[],
                        )
                        await message.answer(
                            "❌ Не удалось получить текст транскрипции. Пожалуйста, попробуйте позже."
                        )
                else:
                    logger.error(
                        f"Некорректный формат ответа транскрипции для пользователя {user_id}"
                    )
                    await log(
                        user_id=user_id,
                        query=message.caption or "",
                        ai_response="Не удалось найти транскрипцию в ответе от сервера",
                        status=0,
                        hashes=[],
                    )
                    await message.answer(
                        "❌ Не удалось найти транскрипцию в ответе от сервера."
                    )
            else:
                logger.error(
                    f"Ошибка получения результата транскрипции для пользователя {user_id}: {response.status}"
                )
                await log(
                    user_id=user_id,
                    query=message.caption or "",
                    ai_response="Не удалось получить результат транскрипции",
                    status=0,
                    hashes=[],
                )
                await message.answer("❌ Не удалось получить результат транскрипции.")

    except Exception as e:
        logger.exception(
            f"Ошибка при получении результата транскрипции для пользователя {user_id}: {e}"
        )
        await log(
            user_id=user_id,
            query=message.caption or "",
            ai_response=str(e),
            status=0,
            hashes=[],
        )
        await message.answer("❌ Ошибка при получении результата транскрипции.")
