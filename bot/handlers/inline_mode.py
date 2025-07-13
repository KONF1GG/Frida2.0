"""Обработчик для inline-режима поиска адресов для тарифов"""
import html
import logging
from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from bot.api.base import utils_client
from bot.utils.decorators import check_and_add_user, send_typing_action

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("tariff"))
@check_and_add_user
@send_typing_action
async def inline_hint(message: Message):
    bot_username = (await message.bot.me()).username
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Начать поиск",
                    switch_inline_query_current_chat=""
                )
            ]
        ]
    )
    await message.answer(
        f"Нажмите кнопку ниже — в строке ввода появится <code>@{bot_username} </code> и вы сможете сразу ввести адрес для поиска информации по тарифам.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.inline_query()
@check_and_add_user
@send_typing_action
async def inline_address_search(inline_query: InlineQuery):
    query = inline_query.query.strip()
    if not query:
        await inline_query.answer([], cache_time=1, switch_pm_text="Введите адрес", switch_pm_parameter="start")
        return

    # Запрос к redis_addresses
    api_response = await utils_client.get_addresses_from_redis(query)
    if not api_response.success or not api_response.data:
        await inline_query.answer(
            [],
            cache_time=1,
            switch_pm_text="Ничего не найдено",
            switch_pm_parameter="notfound"
        )
        return

    addresses = api_response.data.get('addresses')
    if not isinstance(addresses, list) or not addresses:
        await inline_query.answer(
            [],
            cache_time=1,
            switch_pm_text="Ничего не найдено",
            switch_pm_parameter="notfound"
        )
        return

    results = []
    for i, item in enumerate(addresses):
        terr_id = 'terId_' + item.get('territory_id')
        address = item.get("address")
        territory_name = item.get('territory_name')
        if not address:
            continue
        address = html.escape(address.replace('<>', '?'))
        results.append(
            InlineQueryResultArticle(
                id=str(item.get("id", i)),
                title=territory_name,
                description=address,
                input_message_content=InputTextMessageContent(message_text=terr_id)
            )
        )

    await inline_query.answer(results[:50], cache_time=1)


