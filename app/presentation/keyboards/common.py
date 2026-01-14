from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])

def single_button(text: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]]
    )