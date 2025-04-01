from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📚 Текущий урок")],
        [KeyboardButton(text="👥 Домашки других"), KeyboardButton(text="📊 Прогресс")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )

def get_other_homeworks_kb(course_id: str, lesson: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📸 Смотреть работы других учеников",
                callback_data=f"view_hw_{course_id}_{lesson}"
            )]
        ]
    )
    return keyboard