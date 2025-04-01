import asyncio
import logging
import pytz
import os
import re
from datetime import datetime, timedelta
from aiogram import Bot
from src.utils.db import DB_PATH, safe_db_operation, cleanup_old_scheduled_files
from src.config import extract_delay_from_filename  # Changed from get_file_delay
import aiosqlite
from aiogram.types import FSInputFile  # Добавить импорт


logger = logging.getLogger(__name__)

async def send_file(bot: Bot, user_id: int, file_path: str):
    """Send a file to user with proper error handling"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"❌ 4001 File not found: {file_path}")
            return False
            
        # Определяем тип файла по расширению
        ext = file_path.lower().split('.')[-1]
        input_file = FSInputFile(file_path)
        
        if ext in ['txt', 'md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            await bot.send_message(user_id, text, parse_mode=None)
        elif ext in ['jpg', 'jpeg', 'png']:
            await bot.send_photo(user_id, input_file)
        elif ext in ['mp3', 'ogg']:
            await bot.send_audio(user_id, input_file)
        elif ext in ['mp4', 'avi']:
            await bot.send_video(user_id, input_file)
                
        logger.info(f"✅ 4002 File sent successfully: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 4003 Error sending file: {e}", exc_info=True)
        return False

# И в approve_homework (в admin.py) нужно вынести сообщение из цикла:
# Паттерн для поиска задержки в имени файла (например: task_15min.txt или theory_1hour.txt)
DELAY_PATTERN = re.compile(r'_(\d+)(min|hour)\.')

async def send_lesson_files(bot: Bot, user_id: int, course_id: str, lesson: int):
    """Send lesson files to user"""
    logger.info(f"🚀 Attempting to send files for user {user_id}, course {course_id}, lesson {lesson}")
    
    try:
        # Get files that need to be sent
        cursor = await safe_db_operation('''
            SELECT id, file_name, send_at
            FROM scheduled_files
            WHERE user_id = ? AND course_id = ? AND lesson = ? AND sent = 0
            AND send_at <= datetime('now')
        ''', (user_id, course_id, lesson))
        
        files = await cursor.fetchall()
        logger.debug(f"📋 Found {len(files)} files to send")
        
        for file_id, file_name, send_time in files:
            full_path = os.path.join('data', 'courses', course_id, f'lesson{lesson}', file_name)
            logger.debug(f"📎 Attempting to send file: {full_path}")
            
            try:
                if await send_file(bot, user_id, full_path):
                    # Mark as sent
                    await safe_db_operation('''
                        UPDATE scheduled_files 
                        SET sent = 1 
                        WHERE id = ?
                    ''', (file_id,))
                    
            except Exception as e:
                logger.error(f"❌ Error sending file {file_name}: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"💥 Critical error in send_lesson_files: {e}", exc_info=True)
        raise

# Удаляем функцию check_scheduled_files, так как её функциональность 
# теперь полностью покрывается send_lesson_files
async def check_and_send_lessons(bot: Bot):
    while True:
        try:
            result = await safe_db_operation('''
                SELECT COUNT(*)
                FROM homeworks h
                JOIN user_courses uc ON h.user_id = uc.user_id AND h.course_id = uc.course_id
                WHERE h.status = 'approved' 
                AND datetime(h.next_lesson_at) <= datetime('now')
                AND h.next_lesson_sent = 0
            ''')
            count = (await result.fetchone())[0]
            
            if count > 0:
                logger.info(f"2000 | Found {count} pending lessons")
                result = await safe_db_operation('''
                    SELECT 
                        h.user_id, 
                        h.course_id, 
                        h.lesson, 
                        h.next_lesson_at,
                        uc.first_lesson_time,
                        strftime('%s', h.next_lesson_at) - strftime('%s', 'now') as time_diff
                    FROM homeworks h
                    JOIN user_courses uc ON h.user_id = uc.user_id AND h.course_id = uc.course_id
                    WHERE h.status = 'approved' 
                    AND datetime(h.next_lesson_at) <= datetime('now')
                    AND h.next_lesson_sent = 0
                    ORDER BY uc.first_lesson_time ASC, h.lesson ASC
                ''')
                
                pending_lessons = await result.fetchall()
                
                for lesson in pending_lessons:
                    user_id, course_id, lesson_num, next_at, first_time, time_diff = lesson
                    try:
                        await send_lesson_files(bot, user_id, course_id, lesson_num)
                        await safe_db_operation('''
                            UPDATE homeworks 
                            SET next_lesson_sent = 1 
                            WHERE user_id = ? AND course_id = ? AND lesson = ?
                        ''', (user_id, course_id, lesson_num))
                        logger.info(f"2000.4 | Lesson {lesson_num} sent to user {user_id}")
                    except Exception as e:
                        logger.error(f"2000.5 | Failed to send lesson: {e}", exc_info=True)
                    
                    logger.info("2000.6 | Scheduler Check Completed")
                    
        except Exception as e:
            logger.error(f"2000.7 | Scheduler error: {e}", exc_info=True)
            
        await asyncio.sleep(100)


async def schedule_cleanup():
    """Schedule periodic cleanup of old files"""
    while True:
        try:
            await cleanup_old_scheduled_files(7)  # Clean files older than 7 days
            await asyncio.sleep(24 * 60 * 60)  # Run daily
        except Exception as e:
            logger.error(f"Error in cleanup scheduler: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

async def check_next_lessons():
    """Проверяем следующие уроки (и никаких await без async! 🎯)"""
    cursor = await safe_db_operation(
        'YOUR QUERY HERE',
        params,
        return_cursor=True  # This will return the cursor instead of the results
    )
    result = await cursor.fetchone()

def format_next_lesson_time(interval: str) -> str:
    """Форматируем время следующего урока (чтобы было красиво 🎨)"""
    if interval == "7d":
        return "неделю"
    if interval == "14d":
        return "2 недели"
    days = int(interval.replace('d', ''))
    hours = days * 24
    # Правильное склонение для часов
    if hours % 10 == 1 and hours != 11:
        return f"{hours} час"
    elif 2 <= hours % 10 <= 4 and (hours < 10 or hours > 20):
        return f"{hours} часа"
    else:
        return f"{hours} часов"

def parse_next_lesson_time(interval: str) -> datetime:
    """Парсим время следующего урока (без магии, только математика! 🔢)"""
    if interval.endswith('d'):
        days = int(interval[:-1])
        return datetime.now() + timedelta(days=days)
    if interval.endswith('w'):
        weeks = int(interval[:-1])
        return datetime.now() + timedelta(weeks=weeks)
    raise ValueError("Неподдерживаемый формат интервала! 😱")