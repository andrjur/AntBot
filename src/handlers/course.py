import asyncio
from aiogram.types import Message
from src.utils.scheduler import send_lesson_files
from src.utils.courses import get_lesson_files
from src.utils.db import get_user_info

async def handle_start(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Получаем инфу о пользователе через нормальный мок
    user_info = await get_user_info(user_id)
    if not user_info:
        return await message.answer("Пользователь не найден! 😢")
    
    await message.answer(f"Привет, {user_info['name']}! 👋")
    
    # Get current course and lesson
    course_id = "femininity_premium"  # Get from user_courses table
    lesson = 1  # Get from user_courses table
    
    # Start sending lesson files with delays
    await send_lesson_files(message.bot, user_id, course_id, lesson)