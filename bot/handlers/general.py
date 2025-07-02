from utils.decorators import check_and_add_user, send_typing_action

from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode

from config import loading_sticker

from api.milvus import search_milvus
from api.mistral import call_mistral
from api.log import log

router = Router()

@router.message()
@check_and_add_user
@send_typing_action
async def message_handler(message: Message):
    """Обработка обычных сообщений."""
    loading_message = await message.answer_sticker(loading_sticker)        
    try:
        result = await search_milvus(message.from_user.id, message)
        mistral_response = await call_mistral(message.text, result.get('combined_context'), result.get('chat_history'))
        if mistral_response:
            await message.answer(f'{mistral_response}', parse_mode=ParseMode.HTML)
            await log(message.from_user.id, message.text, mistral_response, 1, result.get('hashs'))
        else:
            await message.answer('⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
    
    except Exception as e:
        await log(message.from_user.id, message.text, str(e), 0, result.get('hashs')) if result else await log(message.from_user.id, message.text, str(e), False, [])
        await message.answer('⚠️ Прошу прощения, я не смогла обработать Ваш запрос. Попробуйте позже...', parse_mode=ParseMode.HTML)
    finally:
        await loading_message.delete()
