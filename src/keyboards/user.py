from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками для пользователя"""
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
    """Создает инлайн-клавиатуру для просмотра домашних заданий других учеников"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📸 Смотреть работы других учеников",
                callback_data=f"view_homeworks_{course_id}_{lesson}"
            )]
        ]
    )
    return keyboard

def get_lesson_navigation_kb(course_id: str, current_lesson: int, total_lessons: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для навигации по урокам"""
    buttons = []
    
    # Добавляем кнопки навигации, если есть предыдущий или следующий урок
    nav_buttons = []
    
    if current_lesson > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущий", 
                callback_data=f"lesson_{course_id}_{current_lesson-1}"
            )
        )
    
    if current_lesson < total_lessons:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующий ➡️", 
                callback_data=f"lesson_{course_id}_{current_lesson+1}"
            )
        )
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Добавляем кнопку для отправки домашнего задания
    buttons.append([
        InlineKeyboardButton(
            text="📝 Отправить домашнее задание", 
            callback_data=f"send_homework_{course_id}_{current_lesson}"
        )
    ])
    
    # Добавляем кнопку для просмотра домашек других учеников
    buttons.append([
        InlineKeyboardButton(
            text="👥 Смотреть работы других", 
            callback_data=f"view_homeworks_{course_id}_{current_lesson}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)