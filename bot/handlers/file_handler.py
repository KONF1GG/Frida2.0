from io import StringIO
from aiogram import Router, F
from aiogram.types import Message
import pandas as pd
from utils.decorators import check_and_add_user, send_typing_action
from config import loading_sticker

from api.mistral import call_mistral

router = Router()

@router.message(lambda message: message.document and message.document.mime_type in ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'])
@check_and_add_user
@send_typing_action
async def handle_file(message: Message):
    file = message.document
    loading_message = await message.answer_sticker(loading_sticker)

    try:
        file_info = await message.bot.get_file(file.file_id)
        file_path = await message.bot.download_file(file_info.file_path)

        file_data = file_path.getvalue()
    except Exception as e:
        await message.answer("⚠️ Не удалось загрузить файл. Пожалуйста, попробуйте снова.")
        return

    try:
        if file.mime_type == 'text/csv':
            try:
                try:
                    data = pd.read_csv(StringIO(file_data.decode('utf-8')), delimiter=';')
                except UnicodeDecodeError:
                    data = pd.read_csv(StringIO(file_data.decode('windows-1251', errors='replace')), delimiter=';')
                except Exception as e:
                        data = pd.read_csv(StringIO(file_data.decode('utf-8')), delimiter=',')
            except Exception as e:
                await message.answer(f"⚠️ Ошибка при чтении CSV файла: {str(e)}. Пожалуйста, убедитесь, что файл в формате CSV имеет кодировку UTF-8 или windows-1251, а также желательно использовать разделитель - ';'")
                return

        elif file.mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            try:
                try:
                    data = pd.read_excel(file_path)
                except Exception as e:
                    await message.answer(f"⚠️ Ошибка при чтении Excel файла: {str(e)}. Убедитесь, что файл в формате Excel (.xlsx или .xls) и поддерживается.")
                    return
            except Exception as e:
                await message.answer(f"⚠️ Ошибка при чтении Excel файла: {str(e)}. Попробуйте загрузить другой файл.")
                return

        else:
            await message.answer("⚠️ Неподдерживаемый тип файла. Пожалуйста, загрузите файл в формате CSV или Excel.")
            return

        try:
            csv_buffer = StringIO()
            data.to_csv(csv_buffer, index=False)
            csv_text = csv_buffer.getvalue()
        except Exception as e:
            await message.answer(f"⚠️ Ошибка при конвертации данных в CSV: {str(e)}. Попробуйте еще раз.")
            return

        query = message.caption if message.caption else "Напиши общий отчет по таблице"
        try:
            # message.answer(query)
            mistral_response = await call_mistral(text=query, combined_context=csv_text, input_type='csv')
            if mistral_response:
                await message.answer(mistral_response)
            else:
                await message.answer("⚠️ Произошла ошибка при обработке файла в Mistral.")
        except Exception as e:
            await message.answer(f"⚠️ Произошла ошибка при отправке запроса в Mistral: {str(e)}. Попробуйте позже.")

    except Exception as e:
        await message.answer(f"⚠️ Произошла ошибка при обработке файла: {str(e)}. Пожалуйста, попробуйте снова.")
    finally:
        await loading_message.delete()
