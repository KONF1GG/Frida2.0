"""
Модуль настройки логирования для бота Frida.
Обеспечивает структурированное логирование с различными уровнями.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str, level: int = logging.DEBUG, log_file: Optional[str] = None
) -> logging.Logger:
    """
    Настройка логгера с консольным и файловым выводом

    Args:
        name: Имя логгера
        level: Уровень логирования
        log_file: Путь к файлу логов (опционально)

    Returns:
        Настроенный логгер
    """
    # Создаем логгер
    logger = logging.getLogger(name)

    # Проверяем, не настроен ли уже логгер
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    # Создаем форматтер
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Файловый обработчик (если указан путь)
    if log_file:
        # Создаем директорию для логов если она не существует
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_root_logger(level: int = logging.DEBUG) -> None:
    """
    Настройка корневого логгера для всего приложения

    Args:
        level: Уровень логирования
    """
    # Очищаем существующие обработчики
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Настройка базового логирования
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Принудительно перенастраиваем
    )

    # Настройка уровней для внешних библиотек
    logging.getLogger("aiogram").setLevel(
        logging.INFO
    )  # Показываем некоторые логи aiogram
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Устанавливаем DEBUG для нашего бота
    logging.getLogger("bot").setLevel(logging.DEBUG)

    print(f"🔧 Логирование настроено на уровень: {logging.getLevelName(level)}")


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер с правильной настройкой

    Args:
        name: Имя логгера

    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)
