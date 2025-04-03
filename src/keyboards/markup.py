from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def create_main_menu(course_id=None):
    """Создает инлайн-клавиатуру основного меню с учетом курса"""
    buttons = []
    
    # Кнопка для повторной отправки урока
    buttons.append([
        InlineKeyboardButton(text="📚 Прислать урок заново", callback_data="resend_lesson")
    ])
    
    # Если указан курс, добавляем кнопку для просмотра домашек других учеников
    if course_id:
        buttons.append([
            InlineKeyboardButton(
                text="👥 Смотреть работы других", 
                callback_data=f"view_homeworks_{course_id}_current"
            )
        ])
    
    # Добавляем кнопку помощи
    buttons.append([
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

