import json
import aiosqlite
import os
import logging
from datetime import datetime, timedelta
import pytz
import locale
import asyncio 
from aiosqlite import Error as SQLiteError
from src.config import ADMIN_GROUP_ID, get_lesson_delay
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.utils.course_cache import get_courses_data
from functools import wraps
from typing import Any, Callable
from src.utils.courses import get_lesson_files
# Меняем импорт
from src.utils.db_context import get_db, DB_PATH
from src.utils.text_processor import format_datetime  # Add this import

# Глобальная переменная для соединения
_db_connection = None

async def get_db_connection():
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
    return _db_connection

# Add after get_db_connection function
async def close_db_connection():
    """Close the global database connection"""
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")

# Custom exceptions for error handling 🎯
class BotError(Exception): pass
class CourseNotFoundError(BotError): pass
class HomeworkSubmissionError(BotError): pass
class StateError(BotError): pass
class DatabaseError(BotError): pass
class AdminNotificationError(BotError): pass



# Константы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 5  # seconds


logger = logging.getLogger(__name__)
DB_PATH = "data/bot.db"


try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    # Fallback if Russian locale is not available
    logger.warning("Russian locale not available, using default date format")

  
async def get_active_courses_states(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT 
                uc.course_id,
                us.current_state,
                uc.current_lesson
            FROM user_courses uc
            LEFT JOIN user_states us ON uc.user_id = us.user_id 
                AND uc.course_id = us.current_course
            WHERE uc.user_id = ?
        ''', (user_id,))
        return await cursor.fetchall()

async def submit_homework(user_id: int, course_id: str, lesson: int, file_id: str, bot: Bot = None):
    logger.info(f"📝 Начало отправки ДЗ: user={user_id}, course={course_id}, lesson={lesson}")
    
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            # Проверяем запись курса
            version_id, user_name, first_lesson_time = await verify_course_enrollment(db, user_id, course_id)
            
            # Записываем ДЗ
            await db.execute('''
                INSERT INTO homeworks 
                (user_id, course_id, lesson, status, submission_time, file_id)
                VALUES (?, ?, ?, 'pending', datetime('now'), ?)
            ''', (user_id, course_id, lesson, file_id))
            await db.commit()
            
            # Уведомляем админов
            if bot and ADMIN_GROUP_ID:
                user_data = {
                    'user_id': user_id,
                    'name': user_name,
                    'course_id': course_id,
                    'version_id': version_id,
                    'lesson': lesson
                }
                
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Принять", 
                        callback_data=f"hw_approve_{user_id}_{course_id}_{lesson}"),
                    InlineKeyboardButton(text="❌ Отклонить", 
                        callback_data=f"hw_reject_{user_id}_{course_id}_{lesson}")
                ]])
                
                # Создаем асинхронную задачу для уведомления админов
                asyncio.create_task(
                    notify_admins_with_retry(bot, file_id, user_data, markup)
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке ДЗ: {e}", exc_info=True)
            return False


def cache_with_timeout(timeout_seconds: int = 300):
    """Decorator for caching function results with timeout"""
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache_key = str(args) + str(kwargs)
            now = datetime.now()
            
            if cache_key in cache:
                result, timestamp = cache.get(cache_key)
                if (now - timestamp).total_seconds() < timeout_seconds:
                    return result
                    
            result = func(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
            
        return wrapper
    return decorator

@cache_with_timeout(21600)  # 6 hours cache
def get_courses_data():
    """Get courses data with caching"""
    with open('data/courses.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# Update verify_course_code and get_user_info to use the cache
async def check_existing_enrollment(user_id: int, course_id: str) -> bool:
    try:
        result = await safe_db_operation(
            'SELECT 1 FROM user_courses WHERE user_id = ? AND course_id = ?',
            (user_id, course_id)
        )
        return bool(await result.fetchone())
    except BotError:
        return False

async def enroll_user_in_course(user_id: int, course_id: str, version_id: str) -> bool:
    current_time = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Insert into user_courses
        await safe_db_operation(
            '''INSERT INTO user_courses 
               (user_id, course_id, version_id, current_lesson, first_lesson_time)
               VALUES (?, ?, ?, 1, ?)''',
            (user_id, course_id, version_id, current_time)
        )
        
        # Set initial state
        await safe_db_operation(
            '''INSERT OR REPLACE INTO user_states 
               (user_id, current_state, current_course, current_lesson)
               VALUES (?, 'waiting_homework', ?, 1)''',
            (user_id, course_id)
        )
        return True
    except BotError as e:
        logger.error(f"Failed to enroll user: {e}")
        return False

async def verify_course_code(code: str, user_id: int) -> tuple[bool, str]:
    """Verify course activation code and enroll user if valid"""
    try:
        logger.info(f"🔑 Verifying code '{code}' for user {user_id}")
        courses = get_courses_data()
        
        for course_id, course in courses.items():
            logger.debug(f"📚 Checking course: {course_id}")
            if not course.get('is_active', True):
                logger.debug(f"⏸️ Course {course_id} is not active, skipping")
                continue
                
            for version in course.get('versions', []):
                logger.debug(f"🔍 Checking version {version.get('id')} with code {version.get('code')}")
                if version.get('code') == code:
                    logger.info(f"✅ Found matching code for course {course_id}, version {version['id']}")
                    
                    # Check if already enrolled
                    if await check_existing_enrollment(user_id, course_id):
                        logger.info(f"⚠️ User {user_id} already enrolled in course {course_id}")
                        return False, None
                    
                    # Enroll user
                    if await enroll_user_in_course(user_id, course_id, version['id']):
                        logger.info(f"✅ Successfully enrolled user {user_id} in course {course_id}")
                        return True, course_id
                    else:
                        logger.error(f"❌ Failed to enroll user {user_id} in course {course_id}")
                        return False, None
        
        logger.warning(f"❌ No matching code found: {code}")
        return False, None
        
    except Exception as e:
        logger.error(f"💥 Critical error in verify_course_code: {e}", exc_info=True)
        return False, None



async def safe_db_operation(operation: str, params: tuple = None) -> Any:
    """Safe database operation wrapper"""
    operation_type = operation.strip().upper().split()[0]
    
    try:
        db = await get_db_connection()
        logger.debug(f"🔄 Выполнение {operation_type}: {operation[:100]}...")
        
        try:
            start_time = datetime.now()
            cursor = await db.execute(operation, params or ())
            
            # Для SELECT-запросов возвращаем курсор
            if operation_type == 'SELECT':
                result = cursor
            else:
                await db.commit()
                result = cursor
                
            duration = (datetime.now() - start_time).total_seconds()
            logger.debug(f"✅ {operation_type} выполнен за {duration:.3f}s")
            return result
            
        except SQLiteError as e:
            await db.rollback()
            logger.error(f"❌ Ошибка БД [{operation_type}]: {e}")
            logger.debug(f"Параметры: {params}")
            raise DatabaseError(f"Operation failed: {e}")
            
    except Exception as e:
        logger.error(f"💥 Критическая ошибка БД [{operation_type}]: {e}")
        raise BotError(f"Critical error: {e}")

async def get_db_connection():
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
    return _db_connection

async def close_db_connection():
    """Close the global database connection"""
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")

async def get_user(user_id: int):
    try:
        cursor = await safe_db_operation(
            'SELECT * FROM users WHERE user_id = ?',
            (user_id,)
        )
        return await cursor.fetchone()
    except BotError:
        return None

async def get_user_state(user_id: int) -> tuple[str, str, int]:
    """Get user state from database 🎭"""
    try:
        cursor = await safe_db_operation(
            '''SELECT current_state, current_course, current_lesson 
               FROM user_states 
               WHERE user_id = ?''',
            (user_id,)
        )
        return await cursor.fetchone() or (None, None, None)
    except BotError:
        logger.error(f"Failed to get state for user {user_id}")
        return None, None, None

async def set_user_state(user_id: int, state: str, course_id: str = None, lesson: int = None) -> bool:
    """Set user state in database"""
    try:
        await safe_db_operation(
            '''INSERT OR REPLACE INTO user_states 
               (user_id, current_state, current_course, current_lesson)
               VALUES (?, ?, ?, ?)''',
            (user_id, state, course_id, lesson)
        )
        return True
    except BotError as e:
        logger.error(f"Failed to set user state: {e}")
        return False


# Add after get_user function
async def add_user(user_id: int, name: str) -> bool:
    """Add new user to database with style ✨"""
    try:
        await safe_db_operation(
            '''INSERT OR REPLACE INTO users 
               (user_id, name, registration_date)
               VALUES (?, ?, datetime('now'))''',
            (user_id, name)
        )
        logger.info(f"👋 New user added: {name} (ID: {user_id})")
        return True
    except BotError as e:
        logger.error(f"Failed to add user: {e}")
        return False


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                tokens INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS user_courses (
                user_id INTEGER,
                course_id TEXT,
                version_id TEXT DEFAULT 'basic',
                current_lesson INTEGER DEFAULT 1,
                activation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                first_lesson_time DATETIME,
                PRIMARY KEY (user_id, course_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS homeworks (
                hw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_id TEXT,
                lesson INTEGER,
                status TEXT,
                submission_time DATETIME,
                approval_time DATETIME,
                next_lesson_at DATETIME,
                next_lesson_sent INTEGER DEFAULT 0,
                admin_comment TEXT,
                file_id TEXT,
                admin_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                current_state TEXT,
                current_course TEXT,
                current_lesson INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS token_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS scheduled_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_id TEXT,
                lesson INTEGER,
                file_name TEXT,
                send_at DATETIME,
                sent INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            -- Индексы для оптимизации
            CREATE INDEX IF NOT EXISTS idx_homeworks_user_course 
                ON homeworks(user_id, course_id);
            CREATE INDEX IF NOT EXISTS idx_scheduled_files_user 
                ON scheduled_files(user_id, sent);
            CREATE INDEX IF NOT EXISTS idx_user_states_user 
                ON user_states(user_id, current_course);
            CREATE INDEX IF NOT EXISTS idx_homeworks_status
                ON homeworks(status);  -- Новый индекс
            CREATE INDEX IF NOT EXISTS idx_scheduled_files_date 
                ON scheduled_files(send_at) 
            WHERE sent = 0;
        ''')
        await db.commit()
        logger.info("Database initialization completed")


# Add after notify_admins_with_retry function
async def test_admin_group(bot: Bot) -> bool:
    """Test communication with admin group 🎯"""
    try:
        if not ADMIN_GROUP_ID:
            logger.error("Admin group ID not configured")
            return False
            
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data="admin_test"
            )
        ]])
        
        await bot.send_message(
            ADMIN_GROUP_ID,
            "🔄 Проверка связи с админской группой...",
            reply_markup=markup
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to test admin group: {e}")
        return False


@cache_with_timeout(300)  # Кэш на 5 минут
async def get_user_info(user_id: int) -> str:
    """Get user info with fancy formatting 🎨"""
    try:
        logger.debug(f"Получение информации о пользователе {user_id}")
        cursor = await safe_db_operation('''
            SELECT u.name, uc.course_id, uc.current_lesson, uc.version_id, uc.first_lesson_time
            FROM users u
            LEFT JOIN user_courses uc ON u.user_id = uc.user_id
            WHERE u.user_id = ?
        ''', (user_id,))
        
        user_data = await cursor.fetchone()
        if not user_data:
            return "❌ Пользователь не найден"
        
        name, course_id, lesson, version, start_time = user_data
        
        info = f"👤 {name}"
        
        if course_id:
            courses = get_courses_data()
            course_name = courses[course_id]['name']
            
            start_time_str = ""
            if start_time:
                dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                dt = MOSCOW_TZ.localize(dt)
                start_time_str = f" (начат {format_datetime(dt)})"
            
            info += f"\n📚 Курс: {course_name}{start_time_str}"
            
            delay = get_lesson_delay()
            if delay < 60:
                info += f"\nТестовый режим. Интервал {delay} секунд"
                
            info += f"\n📊 Тариф: {version}"
            info += f"\n📝 Урок: {lesson}"
        else:
            info += "\n📚 Курс не активирован"
            
        return info
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации: {e}")
        return "❌ Ошибка получения данных"

# Add after get_user_info function
async def verify_course_enrollment(db, user_id: int, course_id: str) -> tuple[str, str, str]:
    """Verify user's course enrollment and return version_id, user_name, and first_lesson_time"""
    try:
        cursor = await db.execute('''
            SELECT uc.version_id, u.name, uc.first_lesson_time
            FROM user_courses uc
            JOIN users u ON u.user_id = uc.user_id
            WHERE uc.user_id = ? AND uc.course_id = ?
        ''', (user_id, course_id))
        
        result = await cursor.fetchone()
        if not result:
            raise CourseNotFoundError(f"User {user_id} not enrolled in course {course_id}")
            
        return result
        
    except SQLiteError as e:
        logger.error(f"Database error in verify_course_enrollment: {e}")
        raise DatabaseError(f"Failed to verify enrollment: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in verify_course_enrollment: {e}")
        raise


async def notify_admins_with_retry(bot: Bot, file_id: str, user_data: dict, markup: InlineKeyboardMarkup, 
                                 retry_count: int = DEFAULT_RETRY_COUNT) -> bool:
    """Отправка уведомления админам с повторными попытками"""
    for attempt in range(retry_count):
        try:
            # Отправляем фото с информацией о домашнем задании
            await bot.send_photo(
                chat_id=ADMIN_GROUP_ID,
                photo=file_id,
                caption=(
                    f"📝 Новое домашнее задание!\n"
                    f"👤 Ученик: {user_data['name']}\n"
                    f"📚 Курс: {user_data['course_id']}\n"
                    f"📊 Тариф: {user_data['version_id']}\n"
                    f"📝 Урок: {user_data['lesson']}"
                ),
                reply_markup=markup
            )
            logger.info(f"✅ Домашняя работа отправлена админам для проверки")
            return True
            
        except Exception as e:
            logger.error(f"❌ Попытка {attempt + 1}/{retry_count} отправки админам не удалась: {e}")
            if attempt < retry_count - 1:
                await asyncio.sleep(DEFAULT_RETRY_DELAY)
                
    logger.error("❌ Все попытки отправки админам не удались")
    return False

async def get_pending_homeworks() -> list:
    """Получение списка непроверенных домашних заданий"""
    try:
        cursor = await safe_db_operation('''
            SELECT h.*, u.name as user_name
            FROM homeworks h
            JOIN users u ON h.user_id = u.user_id
            WHERE h.status = 'pending'
            ORDER BY h.submission_time ASC
        ''')
        return await cursor.fetchall()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении pending ДЗ: {e}")
        return []

async def get_next_lesson(user_id: int, course_id: str) -> int:
    """Получение номера следующего урока"""
    try:
        cursor = await safe_db_operation('''
            SELECT current_lesson 
            FROM user_courses 
            WHERE user_id = ? AND course_id = ?
        ''', (user_id, course_id))
        result = await cursor.fetchone()
        return result[0] + 1 if result else 1
    except Exception as e:
        logger.error(f"❌ Ошибка при получении следующего урока: {e}")
        return 1

async def cleanup_old_scheduled_files(days: int = 7):
    """Очистка старых записей из scheduled_files"""
    try:
        await safe_db_operation('''
            DELETE FROM scheduled_files 
            WHERE sent = 1 
            AND send_at < datetime('now', '-? days')
        ''', (days,))
        logger.info(f"🧹 Очищены старые записи из scheduled_files")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке scheduled_files: {e}")


    