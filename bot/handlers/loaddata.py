"""
Обработчик команды /loaddata.
Загружает данные Wiki в базу знаний (только для администраторов).
"""

import logging
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

from bot.api.auth import get_admins
from bot.api.loaddata import upload_wiki_data
from bot.utils.decorators import check_and_add_user, send_typing_action
from bot.config import bot_config

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("loaddata"))
@check_and_add_user
@send_typing_action
async def handle_loaddata_command(message: Message):
    """Обработчик команды загрузки данных Wiki"""
    if not message.from_user:
        logger.warning("Команда /loaddata получена без информации о пользователе")
        return

    user_id = message.from_user.id

    try:
        loading_message = await message.answer_sticker(bot_config.loading_sticker)

        result = await upload_wiki_data(user_id)

        if result["status"] == "success":
            response_text = (
                f"✅ Данные успешно загружены!\n"
                f"📊 Всего записей: {result['data']['data']['total_records']}\n"
            )

            if result["data"]["data"].get("duplicates_removed", 0) > 0:
                response_text += f"🧹 Удалено дубликатов: {result['data']['data']['duplicates_removed']}"

            await message.answer(response_text)
            logger.info(f"Пользователь {user_id} успешно загрузил данные Wiki")

    except RuntimeError as e:
        error_message = str(e)

        if "Ошибка доступа" in error_message:
            try:
                # Получаем список администраторов
                admins = await get_admins()

                # Проверяем и преобразуем данные администраторов
                if not admins or not isinstance(admins, list):
                    raise ValueError("Некорректный формат данных администраторов")

                # Создаем клавиатуру с администраторами
                keyboard_buttons = []
                for admin in admins:
                    try:
                        admin_user_id = admin.get("user_id")
                        username = admin.get("username", "Администратор")
                        if admin_user_id:
                            keyboard_buttons.append(
                                [
                                    InlineKeyboardButton(
                                        text=username,
                                        url=f"tg://user?id={admin_user_id}",
                                    )
                                ]
                            )
                    except Exception as admin_error:
                        logger.error(
                            f"Ошибка обработки данных администратора: {admin_error}"
                        )

                if not keyboard_buttons:
                    await message.answer("⛔ Нет доступных администраторов для связи")
                    return

                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

                await message.answer(
                    "⛔ У вас нет прав на выполнение этой команды.\n"
                    "Свяжитесь с администратором:",
                    reply_markup=keyboard,
                )

                logger.warning(
                    f"Пользователь {user_id} попытался загрузить данные без прав администратора"
                )

            except Exception as admin_error:
                logger.error(f"Ошибка получения списка администраторов: {admin_error}")
                await message.answer(
                    "⛔ У вас нет прав на выполнение этой команды.\n"
                    "Произошла ошибка при получении списка администраторов."
                )

        else:
            await message.answer(f"❌ Ошибка при загрузке данных: {error_message}")
            logger.error(
                f"Ошибка загрузки данных для пользователя {user_id}: {error_message}"
            )

    except ValueError as e:
        await message.answer(f"⚠ Некорректный ответ сервера: {str(e)}")
        logger.error(f"Некорректный ответ сервера для пользователя {user_id}: {str(e)}")

    except Exception as e:
        await message.answer("🚨 Произошла непредвиденная ошибка при загрузке данных")
        logger.exception(
            f"Непредвиденная ошибка в handle_loaddata_command для пользователя {user_id}: {str(e)}"
        )

    finally:
        try:
            await loading_message.delete()
        except Exception as delete_error:
            logger.warning(f"Не удалось удалить loading message: {delete_error}")
