from functools import wraps
from aiogram.types import Message
from databases import PostgreSQL
import config
from aiogram.enums.chat_action import ChatAction

def check_and_add_user(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        postgres = PostgreSQL(**config.postgres_config)
        
        if not postgres.user_exists(message.from_user.id):
            postgres.add_user_to_db(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)

        return await func(message, *args, **kwargs)
    
    return wrapper


def send_typing_action(func):

    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        return await func(message,  *args, **kwargs)

    return wrapper

