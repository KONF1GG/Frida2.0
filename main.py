import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import TOKEN
from bot.handlers import router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from crud import upload_data

async def main():
    logging.basicConfig(level=logging.INFO)
    scheduler = AsyncIOScheduler()

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(router)
    
    commands = [
        {"command": "/start", "description": "Запуск бота"},
        {"command": "/loaddata", "description": "Выгрузить данные Вики"},
        {"command": "/addtopic", "description": "Добавть контекст"}
    ]
    
    scheduler.add_job(
        upload_data,
        trigger=CronTrigger(hour=2, minute=00),
    )
    scheduler.start()
    await bot.set_my_commands(commands)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
if __name__ == "__main__":
    asyncio.run(main())
