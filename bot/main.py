"""
Основной модуль Telegram бота Frida.
Обеспечивает инициализацию и запуск бота с корректным управлением жизненным циклом.
"""

import asyncio
import logging
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
from bot.utils.logger import setup_logger, setup_root_logger

# Настройка корневого логирования в самом начале
setup_root_logger(level=logging.INFO)

# Настройка логирования для модуля
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
            BotCommand(command="start", description="🚀 Запуск бота"),
            BotCommand(command="help", description="📋 Список команд"),
            BotCommand(command="model", description="🤖 Выбрать AI модель"),
            BotCommand(command="tariff", description="🔎 Вопрос по тарифам"),
            BotCommand(command="addtopic", description="📝 Добавить контекст"),
            BotCommand(command="loaddata", description="📦 Выгрузить данные Вики"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info("Команды бота успешно установлены")
        except Exception as e:
            logger.error(f"Ошибка при установке команд: {e}")
            raise

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

            logger.info("Бот успешно инициализирован")

        except Exception as e:
            logger.error(f"Ошибка при инициализации бота: {e}")
            raise

    async def shutdown(self) -> None:
        """Корректное завершение работы"""
        logger.info("Начало процедуры завершения работы...")

        try:
            # Сначала останавливаем диспетчер
            if self.dp:
                try:
                    await self.dp.stop_polling()
                    logger.info("Диспетчер остановлен")
                except Exception as e:
                    logger.warning(f"Ошибка при остановке диспетчера: {e}")

            # Затем закрываем сессию бота
            if self.bot:
                try:
                    await self.bot.session.close()
                    logger.info("Сессия бота закрыта")
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии сессии бота: {e}")

            logger.info("Завершение работы выполнено успешно")

        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")

    async def run(self) -> None:
        """Запуск бота с polling"""
        try:
            await self.startup()

            if not self.dp or not self.bot:
                raise RuntimeError("Бот или диспетчер не инициализированы")

            logger.info("Бот запущен в режиме polling")

            # Создаем задачу для polling
            polling_task = asyncio.create_task(
                self.dp.start_polling(
                    self.bot,
                    skip_updates=True,
                    handle_signals=False,  # Мы сами обрабатываем сигналы
                )
            )

            # Ждем либо завершения polling, либо сигнала завершения
            done, pending = await asyncio.wait(
                [polling_task, asyncio.create_task(self._shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            logger.info("Polling завершен")

        except asyncio.CancelledError:
            logger.info("Polling был отменен")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise
        finally:
            await self.shutdown()


async def main() -> None:
    """Основная функция запуска приложения"""
    app = BotApplication()

    def signal_handler():
        logger.info("Получен сигнал прерывания")
        app._shutdown_event.set()

    # Настройка обработчиков сигналов
    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)
        except Exception as e:
            logger.warning(f"Не удалось установить обработчики сигналов: {e}")

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания от пользователя")
        app._shutdown_event.set()
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        app._shutdown_event.set()
        sys.exit(1)
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        # Для Windows используем ProactorEventLoop для лучшей совместимости
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
