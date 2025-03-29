from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.db import DB_PATH
import aiosqlite
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def schedule_lessons():
    logger.info("5501 | Проверка расписания уроков")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT user_id, course_id, current_lesson 
            FROM user_courses 
            WHERE next_lesson_at <= datetime('now')
        ''')
        for row in await cursor.fetchall():
            user_id, course_id, lesson = row
            await send_lesson(user_id, course_id, lesson)
            logger.info(f"5502 | Отправка урока: {user_id=}, {course_id=}, {lesson=}")