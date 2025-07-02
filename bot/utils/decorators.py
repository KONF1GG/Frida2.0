from functools import wraps
import logging
from aiogram.types import Message
from api.auth import check_and_register_user
from aiogram.enums.chat_action import ChatAction


logger = logging.getLogger(__name__)

def check_and_add_user(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        user = message.from_user
        
        success = await check_and_register_user(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            message=message 
        )
        
        if not success:
            return None
            
        return await func(message, *args, **kwargs)

    return wrapper

def send_typing_action(func):

    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        return await func(message,  *args, **kwargs)

    return wrapper

