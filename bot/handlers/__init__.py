"""
Регистрация всех обработчиков сообщений.
Определяет порядок обработки различных типов сообщений.
"""

from .start import router as start_router
from .add_topic import router as add_topic_router
from .file_handler import router as file_router
from .voice_handler import router as voice_router
from .general import router as general_router
from .loaddata import router as loaddata_router
from .models import router as model_router

from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """
    Регистрация всех обработчиков в диспетчере

    Важно: порядок регистрации имеет значение!
    Более специфичные обработчики должны быть зарегистрированы первыми.
    """
    # Команды (самый высокий приоритет)
    dp.include_router(start_router)
    dp.include_router(loaddata_router)
    dp.include_router(add_topic_router)

    # Специфичные типы контента
    dp.include_router(file_router)
    dp.include_router(voice_router)

    # Новый роутер для выбора модели
    dp.include_router(model_router)

    # Общий обработчик (самый низкий приоритет)
    dp.include_router(general_router)
