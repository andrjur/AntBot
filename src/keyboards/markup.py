from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def create_main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Прислать урок заново", callback_data="resend_lesson")]
    ])
    return kb

async def get_user_info(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT u.name, c.course_id, uc.tier, uc.current_lesson
            FROM users u
            LEFT JOIN user_courses uc ON u.user_id = uc.user_id
            LEFT JOIN courses c ON uc.course_id = c.course_id
            WHERE u.user_id = ?
        ''', (user_id,))
        user_data = await cursor.fetchone()
        
    if not user_data:
        return "👤 Профиль не найден"
        
    name, course_id, tier, lesson = user_data
    with open('src/data/courses.json', 'r', encoding='utf-8') as f:
        courses = json.load(f)
    
    course = courses.get(course_id, {})
    tier_info = course.get('tiers', {}).get(tier, {})
    
    return (f"👤 {name}\n"
            f"📚 Курс: {course.get('name', 'Не активирован')}\n"
            f"🎯 Тариф: {tier_info.get('name', '-')}\n"
            f"📝 Текущий урок: {lesson or 1}")