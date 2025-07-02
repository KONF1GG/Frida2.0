from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from utils.decorators import check_and_add_user, send_typing_action

router = Router()

@router.message(CommandStart())
@check_and_add_user
@send_typing_action
async def command_start_handler(message: Message):
    await message.answer(f"Привет, {message.from_user.full_name}!")