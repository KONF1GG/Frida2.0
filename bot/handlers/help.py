"""
Обработчик команды /help.
Отображает список доступных команд и их описание.
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.utils.decorators import check_and_add_user, send_typing_action

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("help"))
@check_and_add_user
@send_typing_action
async def command_help_handler(message: Message):
    """Обработчик команды /help"""
    if not message.from_user:
        logger.warning("Получена команда /help без информации о пользователе")
        return

    help_message = (
        "📋 <b>Список доступных команд:</b>\n\n"
        
        "🚀 <b>/start</b> - Запуск бота и приветствие\n"
        "Перезапускает бота и показывает приветственное сообщение\n\n"
        
        "📋 <b>/help</b> - Показать это сообщение\n"
        "Отображает список всех команд с описанием\n\n"
        
        "🤖 <b>/model</b> - Выбрать AI модель\n"
        "Позволяет выбрать модель для генерации ответов (Mistral, GPT, DeepSeek)\n\n"
        
        "🔎 <b>/tariff</b> - Вопрос по тарифам\n"
        "Запускает инлайн-режим для поиска адресов и получения информации о тарифах\n\n"
        
        "📝 <b>/addtopic</b> - Добавить контекст\n"
        "Позволяет добавить новую информацию в базу знаний бота\n\n"
        
        "📦 <b>/loaddata</b> - Выгрузить данные Вики\n"
        "Загружает данные из Wiki в базу знаний\n\n"
        
        "💡 <b>Как пользоваться:</b>\n"
        "• Для обычных вопросов просто напишите сообщение\n"
        "• Для поиска тарифов используйте /tariff\n"
        "• Можете отправлять файлы (PDF, Word, Excel) для анализа\n"
        "• Голосовые сообщения также поддерживаются\n\n"
    )

    try:
        await message.answer(help_message, parse_mode="HTML")
        logger.info(f"Пользователь {message.from_user.id} запросил помощь")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения помощи: {e}")