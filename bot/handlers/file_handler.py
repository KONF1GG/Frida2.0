"""
Обработчик файлов CSV и Excel.
Анализирует загруженные таблицы через Mistral AI.
"""

import logging
from io import StringIO, BytesIO
from aiogram import Router
from aiogram.types import Message
import pandas as pd
import chardet

from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.config import bot_config
from bot.api.ai import call_ai
from bot.handlers.models import user_model

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# Поддерживаемые типы файлов
SUPPORTED_MIME_TYPES = [
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]


@router.message(
    lambda message: message.document
    and message.document.mime_type in SUPPORTED_MIME_TYPES
)
@check_and_add_user
@send_typing_action
async def handle_file(message: Message):
    """Обработчик CSV и Excel файлов"""
    if not message.document or not message.from_user:
        logger.warning("Получен файл без документа или пользователя")
        return

    file = message.document
    user_id = message.from_user.id
    

    try:
        # Загрузка файла
        if not message.bot:
            logger.error("Bot объект недоступен")
            return

        file_info = await message.bot.get_file(file.file_id)
        if not file_info.file_path:
            logger.error(f"Не удалось получить путь к файлу для пользователя {user_id}")
            await message.answer("⚠️ Не удалось получить файл. Попробуйте еще раз.")
            return

        downloaded_file = await message.bot.download_file(file_info.file_path)
        if downloaded_file:
            file_data = downloaded_file.read()
            downloaded_file.seek(0)  # Сбрасываем позицию для повторного чтения
        else:
            logger.error(f"Не удалось скачать файл для пользователя {user_id}")
            await message.answer("⚠️ Не удалось загрузить файл. Попробуйте еще раз.")
            return

        logger.info(
            f"Пользователь {user_id} загрузил файл: {file.file_name} ({file.mime_type})"
        )

    except Exception as e:
        logger.error(f"Ошибка при загрузке файла от пользователя {user_id}: {e}")
        await message.answer(
            "⚠️ Не удалось загрузить файл. Пожалуйста, попробуйте снова."
        )
        return

    # Обработка файла в зависимости от типа
    try:
        if file.mime_type == "text/csv":
            data = await _process_csv_file(file_data, user_id)
        elif file.mime_type in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]:
            data = await _process_excel_file(downloaded_file, user_id)
        else:
            await message.answer(
                "⚠️ Неподдерживаемый тип файла. Пожалуйста, загрузите файл в формате CSV или Excel."
            )
            return

        if data is None:
            await message.answer(
                "⚠️ Не удалось обработать файл. Проверьте формат и попробуйте снова."
            )
            return

        try:
            csv_buffer = StringIO()
            data.to_csv(csv_buffer, index=False)
            csv_text = csv_buffer.getvalue()
        except Exception as e:
            logger.error(
                f"Ошибка при конвертации данных в CSV для пользователя {user_id}: {e}"
            )
            await message.answer(
                "⚠️ Ошибка при обработке данных файла. Попробуйте еще раз."
            )
            return

        query = message.caption if message.caption else "Напиши общий отчет по таблице"

        try:
            loading_message = await message.answer_sticker(bot_config.loading_sticker)

            ai_response = await call_ai(
                text=query,
                combined_context=csv_text,
                input_type="csv",
                model=user_model.get(user_id, "mistral-large-latest"),
            )

            if ai_response:
                await message.answer(ai_response)
                logger.info(f"Успешно обработан файл пользователя {user_id}")
            else:
                await message.answer("⚠️ Произошла ошибка при анализе файла в Mistral.")
                logger.warning(
                    f"Mistral не смог обработать файл пользователя {user_id}"
                )

        except Exception as e:
            logger.error(
                f"Ошибка при отправке запроса в Mistral для пользователя {user_id}: {e}"
            )
            await message.answer(
                "⚠️ Произошла ошибка при анализе файла. Попробуйте позже."
            )

    except Exception as e:
        logger.exception(
            f"Неожиданная ошибка при обработке файла пользователя {user_id}: {e}"
        )
        await message.answer(
            "⚠️ Произошла неожиданная ошибка при обработке файла. Пожалуйста, попробуйте снова."
        )

    finally:
        try:
            await loading_message.delete()
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить loading message: {delete_error}")


async def _process_csv_file(file_data: bytes, user_id: int) -> pd.DataFrame | None:
    """Универсальная обработка CSV файла с определением кодировки и разделителя"""
    try:
        # Сначала определяем кодировку автоматически
        detected = chardet.detect(file_data)
        encodings = [detected["encoding"], "utf-8", "windows-1251", "cp1252", "latin-1"]
        encodings = [e for e in encodings if e]  # убрать None

        separators = [";", ",", "\t", "|"]

        for encoding in encodings:
            for separator in separators:
                try:
                    decoded_data = file_data.decode(encoding, errors="replace")
                    data = pd.read_csv(StringIO(decoded_data), delimiter=separator)
                    # Проверяем, что получили разумные данные
                    if len(data.columns) > 1 and len(data) > 0:
                        logger.info(
                            f"CSV файл пользователя {user_id} успешно обработан с кодировкой {encoding} и разделителем '{separator}'"
                        )
                        return data
                except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
                    continue

        # Попробуем открыть как бинарный через pandas (иногда помогает)
        try:
            data = pd.read_csv(
                BytesIO(file_data),
                engine="python",
                encoding="utf-8",
                sep=None,
                on_bad_lines="skip"
            )
            if len(data.columns) > 1 and len(data) > 0:
                logger.info(
                    f"CSV файл пользователя {user_id} успешно обработан как бинарный поток"
                )
                return data
        except Exception:
            pass

        logger.warning(f"Не удалось обработать CSV файл пользователя {user_id}")
        return None

    except Exception as e:
        logger.error(f"Ошибка при обработке CSV файла пользователя {user_id}: {e}")
        return None


async def _process_excel_file(file_stream, user_id: int) -> pd.DataFrame | None:
    """Обработка Excel файла (универсально)"""
    try:
        # Используем BytesIO для повторного чтения
        if hasattr(file_stream, "read"):
            file_stream.seek(0)
            stream = BytesIO(file_stream.read())
        else:
            stream = BytesIO(file_stream)
        data = pd.read_excel(stream)
        logger.info(f"Excel файл пользователя {user_id} успешно обработан")
        return data

    except Exception as e:
        logger.error(f"Ошибка при обработке Excel файла пользователя {user_id}: {e}")
        return None
