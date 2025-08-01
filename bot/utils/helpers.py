"""
Вспомогательные функции для обработки документов и голосовых сообщений.
"""

import asyncio
import logging
import os
import PyPDF2
import aiohttp
import docx
import urllib.parse
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from bot.config import bot_config
from bot.api.milvus import search_milvus
from bot.api.ai import call_ai
from bot.api.log import log
from bot.api.base import core_client
from bot.utils.user_settings import user_model

logger = logging.getLogger(__name__)

# Временное хранилище запросов пользователей для тарифов
user_tariff_queries = {}


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
                            # Используем новую функцию классификации
                            await classify_and_process_query(
                                transcription_text, user_id, message
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
                                    category="Голосовое",
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
                                    category="Голосовое",
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
                            category="Голосовое",
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
                        category="Голосовое",
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
                    category="Голосовое",
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
            category="Голосовое",
        )
        await message.answer("❌ Ошибка при получении результата транскрипции.")


async def classify_and_process_query(
    user_query: str, user_id: int, message: Message
) -> None:
    """
    Классифицирует запрос пользователя и обрабатывает его в зависимости от категории.

    Args:
        user_query: Текстовый запрос пользователя
        user_id: ID пользователя
        message: Сообщение от пользователя
    """
    logger.debug(
        f"🔄 Начинаем классификацию запроса пользователя {user_id}: {user_query[:100]}..."
    )
    try:
        # Категории запросов
        categories = ["Тарифы", "Общий"]

        # Создаем промпт для классификации
        classification_prompt = f"""
        Определи категорию следующего запроса пользователя и извлеки адрес, если он есть.
        
        Доступные категории: {", ".join(categories)}.
        
        Запрос: "{user_query}"
        
        Верни ответ в следующем формате:
        Категория: [название категории]
        Адрес: [извлеченный адрес или "не найден"]

        Если в запросе есть упоминание адреса (улица, дом, населенный пункт, регион, сокращения по типу: ул., д., г., обл., р-н, снт, кв., корп., стр., мкр., пр., ш., пер., пл.), обязательно извлеки его.
        """

        # Классифицируем запрос
        logger.debug("🤖 Отправляем запрос на классификацию к AI модели...")
        selected_model = user_model.get(user_id, "mistral-large-latest")
        classification_result = await call_ai(
            text=classification_prompt,
            combined_context="",
            chat_history="",
            model=selected_model,
        )

        logger.debug(f"📥 Результат классификации: {classification_result}")

        if not classification_result:
            logger.error(
                f"Не удалось классифицировать запрос для пользователя {user_id}"
            )
            await _handle_general_query(user_query, user_id, message)
            return

        # Определяем категорию и извлекаем адрес
        logger.debug("🔍 Начинаем разбор результата классификации...")
        category = None
        extracted_address = None
        classification_lower = classification_result.lower().strip()
        logger.debug(f"📝 Результат для анализа: {classification_lower}")

        # Парсим категорию
        if "тариф" in classification_lower:
            category = "Тарифы"
            logger.debug("✅ Определена категория: Тарифы")
        elif "общий" in classification_lower:
            category = "Общий"
            logger.debug("✅ Определена категория: Общий")
        else:
            category = "Общий"
            logger.debug("⚠️ Категория не определена, используем: Общий")

        # Парсим адрес из ответа LLM
        logger.debug("🏠 Ищем адрес в ответе...")
        lines = classification_result.split("\n")
        for line in lines:
            if "адрес:" in line.lower():
                address_part = line.split(":", 1)[1].strip()
                if address_part and address_part.lower() != "не найден":
                    extracted_address = address_part
                    logger.debug(f"📍 Найден адрес: {extracted_address}")
                break

        if not extracted_address:
            logger.debug("❌ Адрес не найден в ответе")

        logger.info(
            f"Запрос пользователя {user_id} классифицирован как: {category}, извлеченный адрес: {extracted_address}"
        )

        # Обрабатываем запрос в зависимости от категории
        if category == "Тарифы":
            logger.debug("🎯 Переходим к обработке тарифного запроса")
            await _handle_tariff_query(user_query, user_id, message, extracted_address)
        else:
            logger.debug("💬 Переходим к обработке общего запроса")
            await _handle_general_query(user_query, user_id, message)

    except Exception as e:
        logger.exception(
            f"Ошибка при классификации запроса для пользователя {user_id}: {e}"
        )
        await _handle_general_query(user_query, user_id, message)


async def _handle_tariff_query(
    user_query: str,
    user_id: int,
    message: Message,
    extracted_address: str | None = None,
) -> None:
    """
    Обрабатывает запрос категории 'Тарифы'
    """
    try:
        logger.debug(
            f"🏢 Начинаем обработку тарифного запроса для пользователя {user_id}"
        )
        logger.debug(f"📝 Текст запроса: {user_query}")
        logger.debug(f"📍 Извлеченный адрес: {extracted_address}")

        # Ищем адрес в запросе через микросервис
        logger.debug("🔍 Ищем house_id через микросервис...")
        house_id = await _extract_address_from_query(user_query)
        logger.debug(f"🏠 Результат поиска house_id: {house_id}")

        if not house_id:
            # Если микросервис не нашел house_id, но у нас есть извлеченный адрес из LLM
            if extracted_address:
                logger.debug(
                    "📍 Микросервис не нашел house_id, используем извлеченный адрес"
                )
                logger.info(
                    f"Микросервис не нашел house_id, используем извлеченный адрес: {extracted_address}"
                )
                await _handle_tariff_via_redis_addresses(
                    user_query, user_id, message, extracted_address
                )
                return
            # Адрес не найден, просим пользователя указать адрес
            logger.debug("❌ Адрес не найден, запрашиваем у пользователя")
            await message.answer(
                "🏠 Для получения информации о тарифах необходимо указать адрес.\n\n"
                "📍 Пожалуйста, укажите адрес (населенный пункт, улица, дом) для поиска доступных тарифов."
                "Также для достоверного поиска можно воспользоваться командой /tariff",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Запрос о тарифах без указания адреса",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Получаем конкретный адрес по ID
        logger.debug(f"🔍 Получаем адрес по house_id: {house_id}")
        api_response = await core_client.get_address_by_id(house_id)
        logger.debug(f"📋 Ответ API для адреса: {api_response}")

        if not api_response.success or not api_response.data:
            logger.debug("❌ API не вернул данные адреса")
            await message.answer(
                "❌ Не удалось найти адрес по указанному запросу. "
                "Попробуйте уточнить адрес.",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Адрес не найден по ID",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Извлекаем данные адреса
        address_data = api_response.data
        address = address_data.get("address", "")
        territory_id = address_data.get("territory_id", "")
        territory_name = address_data.get("territory_name", "")
        conn_type = address_data.get("conn_type", [])

        logger.debug(f"📍 Адрес: {address}")
        logger.debug(f"🌍 Territory ID: {territory_id}")
        logger.debug(f"🏛️ Territory Name: {territory_name}")
        logger.debug(f"🔌 Типы подключения: {conn_type}")

        if not territory_id:
            logger.debug("❌ Territory ID отсутствует")
            await message.answer(
                "❌ Не удалось получить данные территории для найденного адреса.",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Territory ID не найден",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

            # Сохраняем данные для дальнейшего использования
        logger.debug("💾 Сохраняем данные запроса для дальнейшего использования")
        user_tariff_queries[user_id] = {
            "query": user_query,
            "territory_id": territory_id,
            "address": address,
            "territory_name": territory_name,
            "conn_type": conn_type,
        }

        # Спрашиваем подтверждение адреса
        await _ask_address_confirmation(user_id, message, address, territory_name)

    except Exception as e:
        logger.exception(
            f"Ошибка при обработке тарифного запроса для пользователя {user_id}: {e}"
        )
        error_msg = "❌ Произошла ошибка при обработке запроса о тарифах."
        await message.answer(error_msg)
        await log(
            user_id=user_id,
            query=user_query,
            ai_response=str(e),
            status=0,
            hashes=[],
            category="Тарифы",
        )


async def _ask_address_confirmation(
    user_id: int, message: Message, address: str, territory_name: str
) -> None:
    """
    Спрашивает у пользователя подтверждение найденного адреса
    """
    try:
        # Создаем клавиатуру с подтверждением
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, верно", callback_data=f"addr_confirm_{user_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Нет, не тот", callback_data=f"addr_reject_{user_id}"
                    ),
                ]
            ]
        )

        # Формируем сообщение с найденным адресом
        address_info = f"📍 <b>Найден адрес:</b>\n{address}"
        if territory_name:
            address_info += f"\n🏢 <b>Территория:</b> {territory_name}"

        await message.answer(
            f"{address_info}\n\n❓ <b>Это правильный адрес?</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            f"Запрошено подтверждение адреса для пользователя {user_id}: {address}"
        )

    except Exception as e:
        logger.exception(
            f"Ошибка при запросе подтверждения адреса для пользователя {user_id}: {e}"
        )
        await message.answer(
            "❌ Произошла ошибка при обработке адреса.",
            parse_mode=ParseMode.HTML,
        )


async def handle_address_confirmation(callback_query, confirmed: bool) -> None:
    """
    Обрабатывает подтверждение или отклонение адреса пользователем
    """
    try:
        user_id = callback_query.from_user.id
        message = callback_query.message

        # Получаем сохраненные данные
        user_data = user_tariff_queries.get(user_id)
        if not user_data:
            await callback_query.answer("❌ Данные запроса не найдены")
            return

        if confirmed:
            # Пользователь подтвердил адрес - обрабатываем тарифный запрос
            await callback_query.answer("✅ Адрес подтвержден")

            # Убираем кнопки и показываем что обрабатываем
            await message.edit_text(
                f"✅ <b>Адрес подтвержден:</b> {user_data['address']}\n\n"
                f"⏳ Получаю информацию о тарифах...",
                parse_mode=ParseMode.HTML,
            )

            # Обрабатываем запрос о тарифах
            await _process_confirmed_tariff_request(user_id, message, user_data)
        else:
            # Пользователь отклонил адрес - просим ввести заново
            await callback_query.answer("❌ Попробуйте указать адрес точнее")

            await message.edit_text(
                "❌ <b>Адрес не подходит.</b>\n\n"
                "📍 Пожалуйста, укажите адрес более точно:\n"
                "• Напишите полное название улицы\n"
                "• Укажите номер дома\n"
                "• Можно добавить район или город\n\n"
                '<i>Например: "Краснодар, ул. Красная, 123"</i>',
                parse_mode=ParseMode.HTML,
            )

            # Очищаем сохраненные данные
            if user_id in user_tariff_queries:
                del user_tariff_queries[user_id]

    except Exception as e:
        logger.exception(
            f"Ошибка при обработке подтверждения адреса для пользователя {user_id}: {e}"
        )
        await callback_query.answer("❌ Произошла ошибка")


async def _process_confirmed_tariff_request(
    user_id: int, message: Message, user_data: dict
) -> None:
    """
    Обрабатывает тарифный запрос после подтверждения адреса
    """
    loading_message = None
    try:
        territory_id = user_data["territory_id"]
        user_query = user_data["query"]

        # Показываем загрузочный стикер
        loading_message = await message.answer_sticker(bot_config.loading_sticker)

        # Получаем данные о тарифах из Redis по territory_id
        api_response = await core_client.get_tariffs_from_redis(territory_id)

        if not api_response.success or not api_response.data:
            await message.edit_text(
                "❌ Не удалось найти информацию о тарифах для данного адреса. "
                "Возможно, услуги на этой территории пока недоступны.",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Тарифы не найдены для territory_id",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Фильтруем тарифы по доступным типам подключения
        tariff_info = api_response.data
        available_conn_types = user_data.get("conn_type", [])

        if available_conn_types and isinstance(tariff_info, dict):
            # Создаем отфильтрованную копию тарифов
            filtered_tariff_info = {}
            for conn_type in available_conn_types:
                if conn_type in tariff_info:
                    filtered_tariff_info[conn_type] = tariff_info[conn_type]

            if filtered_tariff_info:
                tariff_info = filtered_tariff_info
                logger.info(
                    f"Отфильтрованы тарифы для типов подключения: {available_conn_types}"
                )
            else:
                logger.warning(
                    f"Не найдено тарифов для доступных типов подключения: {available_conn_types}"
                )

        # Генерируем ответ с информацией о тарифах
        tariff_context = f"Информация о тарифах для территории {territory_id} ({user_data.get('territory_name', '')}):\n{str(tariff_info)}"

        selected_model = user_model.get(user_id, "mistral-large-latest")
        ai_response = await call_ai(
            text=user_query,
            combined_context=tariff_context,
            chat_history="",
            model=selected_model,
        )

        if ai_response:
            status_bar = (
                f"📍 <b>{user_data.get('territory_name', 'Территория')}</b>\n\n"
            )

            # Показываем результат
            await message.edit_text(status_bar + ai_response, parse_mode=ParseMode.HTML)

            await log(
                user_id=user_id,
                query=user_query,
                ai_response=ai_response,
                status=1,
                hashes=[],
                category="Тарифы",
            )
            logger.info(f"Успешно обработан тарифный запрос пользователя {user_id}")
        else:
            error_msg = (
                "⚠️ Произошла ошибка при обработке вопроса о тарифах. Попробуйте позже."
            )
            await message.edit_text(error_msg, parse_mode=ParseMode.HTML)
            await log(
                user_id=user_id,
                query=user_query,
                ai_response=error_msg,
                status=0,
                hashes=[],
                category="Тарифы",
            )

        # Очищаем сохраненные данные
        if user_id in user_tariff_queries:
            del user_tariff_queries[user_id]

    except Exception as e:
        logger.exception(
            f"Ошибка при обработке подтвержденного тарифного запроса для пользователя {user_id}: {e}"
        )
        error_msg = "❌ Произошла ошибка при обработке запроса о тарифах."
        try:
            await message.edit_text(error_msg)
        except Exception:
            await message.answer(error_msg)
        await log(
            user_id=user_id,
            query=user_data.get("query", ""),
            ai_response=str(e),
            status=0,
            hashes=[],
        )

    finally:
        # Удаляем загрузочный стикер
        if loading_message:
            try:
                await loading_message.delete()
            except Exception as delete_error:
                logger.warning(f"Не удалось удалить loading message: {delete_error}")


async def _handle_general_query(
    user_query: str, user_id: int, message: Message
) -> None:
    """
    Обрабатывает общие запросы через векторную базу знаний
    """
    try:
        result = await search_milvus(user_id, message)

        if result:
            selected_model = user_model.get(user_id, "mistral-large-latest")
            ai_response = await call_ai(
                user_query,
                result.get("combined_context", ""),
                result.get("chat_history", ""),
                model=selected_model,
            )

            if ai_response:
                await message.answer(ai_response, parse_mode=ParseMode.HTML)
                await log(
                    user_id=user_id,
                    query=user_query,
                    ai_response=ai_response,
                    status=1,
                    hashes=result.get("hashs", []),
                    category="Общий",
                )
                logger.info(f"Успешно обработан общий запрос пользователя {user_id}")
            else:
                error_msg = "⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже..."
                await message.answer(error_msg, parse_mode=ParseMode.HTML)
                await log(
                    user_id=user_id,
                    query=user_query,
                    ai_response=error_msg,
                    status=0,
                    hashes=result.get("hashs", []),
                    category="Общий",
                )
        else:
            await message.answer(
                "❌ Ошибка при поиске контекста",
                parse_mode=ParseMode.HTML,
            )

    except Exception as e:
        logger.exception(
            f"Ошибка при обработке общего запроса для пользователя {user_id}: {e}"
        )
        await log(
            user_id=user_id,
            query=user_query,
            ai_response=str(e),
            status=0,
            hashes=[],
            category="Общий",
        )
        await message.answer(
            "❌ Произошла ошибка при обработке запроса",
            parse_mode=ParseMode.HTML,
        )


async def _extract_address_from_query(user_query: str) -> str | None:
    """
    Извлекает адрес из запроса пользователя и возвращает house_id

    Args:
        user_query: Запрос пользователя

    Returns:
        house_id или None если адрес не найден
    """
    try:
        # Кодируем запрос для URL
        encoded_query = urllib.parse.quote(user_query)

        # Формируем URL для запроса к микросервису адресов
        url = f"http://192.168.110.115:8888/adress?query={encoded_query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"accept": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    house_id = data.get("houseid")

                    if house_id:
                        logger.info(
                            f"Найден house_id: {house_id} для запроса: {user_query}"
                        )
                        return house_id
                    else:
                        logger.info(
                            f"house_id не найден в ответе для запроса: {user_query}"
                        )
                        return None
                else:
                    logger.error(f"Ошибка при запросе адреса: HTTP {response.status}")
                    return None

    except Exception as e:
        logger.exception(f"Ошибка при извлечении адреса из запроса '{user_query}': {e}")
        return None


async def _handle_tariff_via_redis_addresses(
    user_query: str, user_id: int, message: Message, extracted_address: str
) -> None:
    """
    Обрабатывает тарифный запрос через redis_addresses (как в команде /tariff)
    """
    try:
        # Ищем адреса через redis_addresses
        api_response = await core_client.get_addresses_from_redis(extracted_address)

        if not api_response.success or not api_response.data:
            await message.answer(
                "❌ Не удалось найти адреса по указанному запросу. "
                "Попробуйте уточнить адрес или воспользуйтесь командой /tariff",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Адреса не найдены через redis_addresses",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        addresses = api_response.data.get("addresses")
        if not isinstance(addresses, list) or not addresses:
            await message.answer(
                "❌ Не найдено адресов по вашему запросу. "
                "Попробуйте уточнить адрес или воспользуйтесь командой /tariff",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Пустой список адресов",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Берем первый найденный адрес
        first_address = addresses[0]
        territory_id = first_address.get("territory_id")
        territory_name = first_address.get("territory_name", "")

        if not territory_id:
            await message.answer(
                "❌ Не удалось получить данные территории для найденного адреса.",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Territory ID не найден в первом адресе",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Получаем тарифы для территории
        tariffs_response = await core_client.get_tariffs_from_redis(territory_id)

        if not tariffs_response.success or not tariffs_response.data:
            await message.answer(
                "❌ Не удалось найти информацию о тарифах для данного адреса. "
                "Возможно, услуги на этой территории пока недоступны.",
                parse_mode=ParseMode.HTML,
            )
            await log(
                user_id=user_id,
                query=user_query,
                ai_response="Тарифы не найдены для territory_id из redis_addresses",
                status=0,
                hashes=[],
                category="Тарифы",
            )
            return

        # Генерируем ответ с информацией о тарифах
        tariff_info = tariffs_response.data
        tariff_context = f"Информация о тарифах для территории {territory_id} ({territory_name}):\n{str(tariff_info)}"

        selected_model = user_model.get(user_id, "mistral-large-latest")
        ai_response = await call_ai(
            text=user_query,
            combined_context=tariff_context,
            chat_history="",
            model=selected_model,
        )

        if ai_response:
            status_bar = f"📍 <b>{territory_name}</b>\n\n"

            await message.answer(status_bar + ai_response, parse_mode=ParseMode.HTML)

            await log(
                user_id=user_id,
                query=user_query,
                ai_response=ai_response,
                status=1,
                hashes=[],
                category="Тарифы",
            )
            logger.info(
                f"Успешно обработан тарифный запрос через redis_addresses для пользователя {user_id}"
            )
        else:
            error_msg = (
                "⚠️ Произошла ошибка при обработке вопроса о тарифах. Попробуйте позже."
            )
            await message.answer(error_msg, parse_mode=ParseMode.HTML)
            await log(
                user_id=user_id,
                query=user_query,
                ai_response=error_msg,
                status=0,
                hashes=[],
            )

    except Exception as e:
        logger.exception(
            f"Ошибка при обработке тарифного запроса через redis_addresses для пользователя {user_id}: {e}"
        )
        error_msg = "❌ Произошла ошибка при обработке запроса о тарифах."
        await message.answer(error_msg, parse_mode=ParseMode.HTML)
        await log(
            user_id=user_id,
            query=user_query,
            ai_response=str(e),
            status=0,
            hashes=[],
        )
