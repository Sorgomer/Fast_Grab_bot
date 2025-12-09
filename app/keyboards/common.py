from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def cancel_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛑 Отменить",
                    callback_data=f"cancel:{task_id}",
                )
            ]
        ]
    )