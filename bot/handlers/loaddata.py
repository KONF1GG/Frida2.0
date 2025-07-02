import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

from api.auth import get_admins
from api.loaddata import upload_wiki_data
from utils.decorators import check_and_add_user, send_typing_action


from config import loading_sticker

router = Router()

logger = logging.getLogger(__name__)

@router.message(Command("loaddata"))
@check_and_add_user
@send_typing_action
async def handle_loaddata_command(message: Message):
    loading_message = await message.answer_sticker(loading_sticker)
    
    try:
        result = await upload_wiki_data(message.from_user.id)
        
        if result["status"] == "success":
            response_text = (
                f"✅ Данные успешно загружены!\n"
                f"📊 Всего записей: {result['data']['data']['total_records']}\n"
            )
            
            if result['data']['data'].get('duplicates_removed', 0) > 0:
                response_text += (
                    f"🧹 Удалено дубликатов: {result['data']['data']['duplicates_removed']}"
                )
            
            await message.answer(response_text)
            
    except RuntimeError as e:
        error_message = str(e)
        if "Ошибка доступа" in error_message:
            try:
                # Получаем список администраторов
                admins = await get_admins()
                
                # Проверяем и преобразуем данные администраторов
                if not admins or not isinstance(admins, list):
                    raise ValueError("Некорректный формат данных администраторов")
                
                # Создаем клавиатуру с администраторами
                keyboard_buttons = []
                for admin in admins:
                    try:
                        user_id = admin.get('user_id')
                        username = admin.get('username', 'Администратор')
                        if user_id:
                            keyboard_buttons.append(
                                [InlineKeyboardButton(
                                    text=username,
                                    url=f'tg://user?id={user_id}'
                                )]
                            )
                    except Exception as admin_error:
                        logger.error(f"Error processing admin data: {admin_error}")

                if not keyboard_buttons:
                    await message.answer("⛔ Нет доступных администраторов для связи")
                    return
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                await message.answer(
                    '⛔ У вас нет прав на выполнение этой команды.\n'
                    'Свяжитесь с администратором:',
                    reply_markup=keyboard
                )
                
            except Exception as admin_error:
                logger.error(f"Error getting admins list: {admin_error}")
                await message.answer(
                    '⛔ У вас нет прав на выполнение этой команды.\n'
                    'Произошла ошибка при получении списка администраторов.'
                )
                
        else:
            await message.answer(f'❌ Ошибка при загрузке данных: {error_message}')
            
    except ValueError as e:
        await message.answer(f'⚠ Некорректный ответ сервера: {str(e)}')
        
    except Exception as e:
        await message.answer('🚨 Произошла непредвиденная ошибка при загрузке данных')
        logger.error(f"Unexpected error in handle_loaddata_command: {str(e)}", exc_info=True)
        
    finally:
        await loading_message.delete()