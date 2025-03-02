import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import TOKEN
from bot.handlers import router

async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(router)
    
    commands = [
        {"command": "/start", "description": "Запуск бота"},
        {"command": "/loaddata", "description": "Выгрузить данные Вики"},
        {"command": "/addtopic", "description": "Добавть контекст"}
    ]
    
    await bot.set_my_commands(commands)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
