import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from handlers import register_all_handlers

from config import TOKEN, TEST_TOKEN
import logging

async def main():
    logging.basicConfig(level=logging.DEBUG)

    bot = Bot(token=TEST_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    register_all_handlers(dp)

    commands = [
        {"command": "/start", "description": "Запуск бота"},
        {"command": "/loaddata", "description": "Выгрузить данные Вики"},
        {"command": "/addtopic", "description": "Добавть контекст"}
    ]
    
    await bot.set_my_commands(commands)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
