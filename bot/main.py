"""
Основной модуль Telegram бота Frida.
Обеспечивает инициализацию и запуск бота с корректным управлением жизненным циклом.
"""

import asyncio
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand

from bot.handlers import register_all_handlers
from bot.config import bot_config
from bot.utils.logger import setup_logger

# Настройка логирования
logger = setup_logger(__name__)


class BotApplication:
    """Класс приложения бота с управлением жизненным циклом"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._shutdown_event = asyncio.Event()

    async def _create_bot(self) -> Bot:
        """Создание экземпляра бота"""
        session = AiohttpSession()
        return Bot(
            token=bot_config.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=session,
        )

    async def _setup_commands(self) -> None:
        """Настройка команд бота"""
        if not self.bot:
            raise RuntimeError("Бот не инициализирован")

        commands = [
            BotCommand(command="start", description="Запуск бота"),
            BotCommand(command="loaddata", description="Выгрузить данные Вики"),
            BotCommand(command="addtopic", description="Добавить контекст"),
            BotCommand(command="model", description="Выбрать AI модель"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info("Команды бота успешно установлены")
        except Exception as e:
            logger.error(f"Ошибка при установке команд: {e}")
            raise

    async def _setup_signal_handlers(self) -> None:
        """Настройка обработчиков сигналов для graceful shutdown"""
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._signal_handler)

    def _signal_handler(self) -> None:
        """Обработчик сигналов завершения"""
        logger.info("Получен сигнал завершения")
        self._shutdown_event.set()

    async def startup(self) -> None:
        """Инициализация приложения"""
        logger.info("Запуск бота Frida...")

        try:
            # Создание бота и диспетчера
            self.bot = await self._create_bot()
            self.dp = Dispatcher()

            # Регистрация обработчиков
            register_all_handlers(self.dp)
            logger.info("Обработчики зарегистрированы")

            # Настройка команд
            await self._setup_commands()

            # Настройка обработчиков сигналов
            await self._setup_signal_handlers()

            logger.info("Бот успешно инициализирован")

        except Exception as e:
            logger.error(f"Ошибка при инициализации бота: {e}")
            raise

    async def shutdown(self) -> None:
        """Корректное завершение работы"""
        logger.info("Начало процедуры завершения работы...")

        try:
            if self.bot:
                await self.bot.session.close()
                logger.info("Сессия бота закрыта")

            logger.info("Завершение работы выполнено успешно")

        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")

    async def run(self) -> None:
        """Запуск бота с polling"""
        try:
            await self.startup()

            if not self.dp or not self.bot:
                raise RuntimeError("Бот или диспетчер не инициализированы")

            # Запуск polling в отдельной задаче
            polling_task = asyncio.create_task(
                self.dp.start_polling(self.bot, skip_updates=True)
            )

            logger.info("Бот запущен в режиме polling")

            # Ожидание сигнала завершения
            await self._shutdown_event.wait()

            # Остановка polling
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("Polling остановлен")

        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise
        finally:
            await self.shutdown()


async def main() -> None:
    """Основная функция запуска приложения"""
    app = BotApplication()

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания от пользователя")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
