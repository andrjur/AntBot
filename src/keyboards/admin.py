from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_hw_review_kb(hw_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{hw_id}"),
            InlineKeyboardButton("❌ Отказать", callback_data=f"reject_{hw_id}")
        ],
        [
            InlineKeyboardButton("📝 Одобрить с комментарием", 
                               callback_data=f"approve_comment_{hw_id}"),
            InlineKeyboardButton("📝 Отказать с комментарием", 
                               callback_data=f"reject_comment_{hw_id}")
        ]
    ])