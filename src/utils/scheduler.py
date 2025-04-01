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


logger = logging.getLogger(__name__)

async def send_file(bot: Bot, user_id: int, file_path: str):
    """Send a file to user with proper error handling"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"❌ 4001 File not found: {file_path}")
            return False
            
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            
        await bot.send_message(user_id, text)
        logger.info(f"✅ 4002 File sent successfully: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 4003 Error sending file: {e}", exc_info=True)
        return False

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
                if not os.path.exists(full_path):
                    logger.error(f"❌ File not found: {full_path}")
                    continue
                    
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Send the file content
                await bot.send_message(user_id, content)
                logger.info(f"✅ Successfully sent file {file_name} to user {user_id}")
                
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

async def check_scheduled_files(bot: Bot):
    logger.info("2000999 Starting file scheduler")
    while True:
        try:
            result = await safe_db_operation('''
                SELECT * FROM scheduled_files 
                WHERE sent = 0 AND send_at <= datetime('now')
            ''')
            files = await result.fetchall()
            
            if files:
                logger.info(f"2200 Found {len(files)} files ready to send")
                for file in files:
                    user_id = file[1]
                    course_id = file[2]
                    lesson = file[3]
                    file_name = file[4]
                    
                    file_path = os.path.join('data', 'courses', course_id, f'lesson{lesson}', file_name)
                    logger.info(f"2201 Sending file to user {user_id}: {file_path}")
                    
                    try:
                        if await send_file(bot, user_id, file_path):
                            await safe_db_operation('''
                                UPDATE scheduled_files 
                                SET sent = 1 
                                WHERE id = ?
                            ''', (file[0],))
                            logger.info(f"2203 File sent successfully")
                    except Exception as e:
                        logger.error(f"2204 Error sending file {file_path}: {e}")
                else:
                    logger.debug("2205 No files ready to send")
                    
        except Exception as e:
            logger.error(f"2206 Scheduler error: {e}")
            
        await asyncio.sleep(35)


async def schedule_cleanup():
    """Schedule periodic cleanup of old files"""
    while True:
        try:
            await cleanup_old_scheduled_files(7)  # Clean files older than 7 days
            await asyncio.sleep(24 * 60 * 60)  # Run daily
        except Exception as e:
            logger.error(f"Error in cleanup scheduler: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error