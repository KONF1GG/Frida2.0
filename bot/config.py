import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    """Конфигурация бота"""

    token: str
    test_token: str
    api_key: str
    whisper_api: str
    utils_url: str
    loading_sticker: str = (
        "CAACAgIAAxkBAAJMS2YHPrVKVmiyNhVR3J5vQE2Qpu-kAAIjAAMoD2oUJ1El54wgpAY0BA"
    )


@dataclass(frozen=True)
class DatabaseConfig:
    """Конфигурация базы данных"""

    # MySQL
    mysql_host: Optional[str] = None
    mysql_port: Optional[str] = None
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    mysql_db: Optional[str] = None

    # PostgreSQL
    postgres_host: Optional[str] = None
    postgres_port: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None


def get_bot_config() -> BotConfig:
    """Получить конфигурацию бота"""
    required_vars = ["TOKEN", "TEST_TOKEN", "API_KEY", "WHISPER_API", "UTILS_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
        )

    return BotConfig(
        token=str(os.getenv("TOKEN")),
        test_token=str(os.getenv("TEST_TOKEN")),
        api_key=str(os.getenv("API_KEY")),
        whisper_api=str(os.getenv("WHISPER_API")),
        utils_url=str(os.getenv("UTILS_URL")),
    )


def get_database_config() -> DatabaseConfig:
    """Получить конфигурацию базы данных"""
    return DatabaseConfig(
        mysql_host=os.getenv("HOST_MYSQL"),
        mysql_port=os.getenv("PORT_MYSQL"),
        mysql_user=os.getenv("USER_MYSQL"),
        mysql_password=os.getenv("PASSWORD_MYSQL"),
        mysql_db=os.getenv("DB_MYSQL"),
        postgres_host=os.getenv("POSTGRES_HOST"),
        postgres_port=os.getenv("POSTGRES_PORT"),
        postgres_user=os.getenv("POSTGRES_USER"),
        postgres_password=os.getenv("POSTGRES_PASSWORD"),
        postgres_db=os.getenv("POSTGRES_DB"),
    )


# Глобальные экземпляры конфигурации
bot_config = get_bot_config()
db_config = get_database_config()

# Обратная совместимость (для существующих импортов)
TOKEN = bot_config.token
TEST_TOKEN = bot_config.test_token
API_KEY = bot_config.api_key
WHISPER_API = bot_config.whisper_api
UTILS_URL = bot_config.utils_url
loading_sticker = bot_config.loading_sticker
