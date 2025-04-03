from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_hw_review_kb(user_id, course_id, lesson):
    """Создает клавиатуру для проверки домашнего задания"""
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Одобрить", 
                callback_data=f"hw_approve_{user_id}_{course_id}_{lesson}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить", 
                callback_data=f"hw_reject_{user_id}_{course_id}_{lesson}"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_rejection_reasons_kb():
    """Создает клавиатуру с причинами отказа в домашнем задании"""
    buttons = [
        [
            InlineKeyboardButton(
                text="😳 Слишком смущает", 
                callback_data="reject_reason_shy"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚩 Коммунизм не построишь", 
                callback_data="reject_reason_communism"
            )
        ],
        [
            InlineKeyboardButton(
                text="💪 Возьми себя в руки", 
                callback_data="reject_reason_focus"
            )
        ],
        [
            InlineKeyboardButton(
                text="🎲 Случайная мотивация", 
                callback_data="reject_reason_random"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_main_kb():
    """Создает основную клавиатуру для администратора"""
    buttons = [
        [
            InlineKeyboardButton(
                text="📊 Статистика", 
                callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Проверить домашние задания", 
                callback_data="admin_check_hw"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Управление пользователями", 
                callback_data="admin_manage_users"
            )
        ],
        [
            InlineKeyboardButton(
                text="📚 Управление курсами", 
                callback_data="admin_manage_courses"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_course_management_kb():
    """Создает клавиатуру для управления курсами"""
    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Добавить курс", 
                callback_data="admin_add_course"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Обновить материалы", 
                callback_data="admin_update_materials"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика курсов", 
                callback_data="admin_course_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data="admin_back_to_main"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_management_kb():
    """Создает клавиатуру для управления пользователями"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🔍 Найти пользователя", 
                callback_data="admin_find_user"
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить пользователя", 
                callback_data="admin_add_user"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика пользователей", 
                callback_data="admin_user_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data="admin_back_to_main"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)