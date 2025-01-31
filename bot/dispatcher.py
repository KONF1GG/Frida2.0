from aiogram import Dispatcher
from Frida_bot.bot.handlers import router

dp = Dispatcher()
dp.include_router(router)
