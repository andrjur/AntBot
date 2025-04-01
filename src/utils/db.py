__all__ = [
    'add_user',
    'get_user',
    'safe_db_operation',
    'verify_course_code',
    'enroll_user_in_course',
    'submit_homework',
    'get_user_state',
    'set_user_state',
    'get_user_info',
    'verify_course_enrollment',
    'init_db',
    'close_db_connection',
    'get_db_connection',
    'BotError',
    'CourseNotFoundError',
    'DatabaseError'
]
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

# Исправляем функцию verify_course_code, чтобы она проверяла коды в базе данных
async def verify_course_code(code: str, user_id: int) -> tuple[bool, str]:
    """Проверка кода курса и активация"""
    try:
        code = code.strip().lower()
        
        # Ищем курс по коду в базе данных
        result = await safe_db_operation(
            '''SELECT id FROM courses 
               WHERE LOWER(code) = ? 
               AND NOT EXISTS (
                   SELECT 1 FROM user_courses 
                   WHERE user_id = ? AND course_id = id
               )''',
            (code, user_id),
            fetch_one=True
        )
        
        if not result:
            # Проверяем, активирован ли уже курс с таким кодом
            course_exists = await safe_db_operation(
                '''SELECT 1 FROM courses c
                   JOIN user_courses uc ON c.id = uc.course_id
                   WHERE LOWER(c.code) = ? AND uc.user_id = ?''',
                (code, user_id),
                fetch_one=True
            )
            
            if course_exists:
                return False, "Этот курс уже активирован"
            else:
                return False, "Неверный код курса"
        
        # Получаем ID курса и активируем его
        course_id = result[0]
        
        # Определяем версию курса (тариф)
        if '_' in course_id:
            base_id, version_id = course_id.split('_', 1)
        else:
            base_id, version_id = course_id, 'basic'
        
        # Активируем курс
        success = await enroll_user_in_course(user_id, base_id, version_id)
        if success:
            return True, base_id
        else:
            return False, "Ошибка активации курса"
        
    except Exception as e:
        logger.error(f"Course verification error: {str(e)}", exc_info=True)
        return False, "Ошибка активации курса"

# Добавляем вспомогательную функцию для проверки существующей активации
async def check_existing_enrollment(user_id: int, course_id: str) -> bool:
    """Проверяет, активирован ли уже курс для пользователя"""
    try:
        result = await safe_db_operation(
            "SELECT 1 FROM user_courses WHERE user_id = ? AND course_id = ?",
            (user_id, course_id),
            fetch_one=True
        )
        return bool(result)
    except Exception as e:
        logger.error(f"Error checking enrollment: {e}")
        return False



async def safe_db_operation(query: str, params: tuple = None, fetch_one: bool = False):
    """Безопасное выполнение операций с БД (и никаких фокусов! 🎩)"""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute(query, params) if params else await db.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                if fetch_one:
                    result = await cursor.fetchone()
                else:
                    result = await cursor.fetchall()
                await cursor.close()  # ← Важно закрывать курсор!
                return result  # Теперь возвращаем данные, а не курсор
            
            await db.commit()
            return None
            
        except Exception as e:
            operation_type = "SELECT" if query.strip().upper().startswith("SELECT") else \
                           "INSERT" if query.strip().upper().startswith("INSERT") else \
                           "UPDATE" if query.strip().upper().startswith("UPDATE") else \
                           "DELETE" if query.strip().upper().startswith("DELETE") else \
                           "UNKNOWN"
            
            logger.error(f"💥 Критическая ошибка БД [{operation_type}]: {e}")
            raise

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

MIN_USER_FIELDS = 3  # user_id, name, registration_date

async def add_user(user_id: int, name: str) -> bool:
    """Add or update user in database 🆔"""
    try:
        # Use same connection pattern as other operations
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)",
                (user_id, name)
            )
            await db.commit()
            logger.info(f"User {user_id} added/updated successfully")
            return True
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
        return False

async def get_user(user_id: int):
    try:
        # Direct connection instead of safe_db_operation for consistency
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                'SELECT * FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = await cursor.fetchone()
            if result and len(result) >= MIN_USER_FIELDS:
                return result
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
        return None

async def get_user_state(user_id: int) -> tuple[str, str, int]:
    """Get user state from database 🎭"""
    try:
        # Используем новый подход без курсора
        result = await safe_db_operation(
            '''SELECT current_state, current_course, current_lesson 
               FROM user_states 
               WHERE user_id = ?''',
            (user_id,),
            fetch_one=True
        )
        return result or (None, None, None)
    except Exception as e:
        logger.error(f"Failed to get state for user {user_id}: {e}")
        return (None, None, None)

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




async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Add this index for course codes
            CREATE INDEX IF NOT EXISTS idx_courses_code 
                ON courses(code);

            -- Existing tables below...
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
        
        # Load courses from JSON
        try:
            # Use relative paths that work on both Windows and Linux
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Go up to project root
            courses_path = os.path.join(base_dir, 'data', 'courses.json')
            
            # Check if the courses.json file exists
            if not os.path.exists(courses_path):
                logger.warning(f"Courses file not found at {courses_path}, trying alternative location")
                courses_path = os.path.join(base_dir, 'data', 'courses', 'courses.json')
            
            logger.info(f"Loading courses from: {courses_path}")
            
            with open(courses_path, 'r', encoding='utf-8') as f:
                courses = json.load(f)
                
                for course_id, course_data in courses.items():
                    # Verify course structure
                    if 'tiers' not in course_data:
                        logger.warning(f"Skipping invalid course {course_id}")
                        continue
                    
                    # Set course directory path for course-specific files
                    course_dir = os.path.join(base_dir, 'data', 'courses', course_id)
                    if not os.path.exists(course_dir):
                        os.makedirs(course_dir, exist_ok=True)
                        logger.info(f"Created course directory: {course_dir}")
                        
                    # Insert main course using first tier
                    first_tier = next(iter(course_data['tiers'].values()), {})
                    await db.execute('''
                        INSERT OR REPLACE INTO courses (id, name, code, description)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        course_id,
                        course_data['name'],
                        first_tier.get('code', 'default_code'),
                        course_data.get('description', '')
                    ))
                    
                    # Insert course tiers
                    for tier_name, tier_data in course_data.get('tiers', {}).items():
                        tier_id = f"{course_id}_{tier_name}"
                        await db.execute('''
                            INSERT OR REPLACE INTO courses (id, name, code, description)
                            VALUES (?, ?, ?, ?)
                        ''', (
                            tier_id,
                            f"{course_data['name']} ({tier_data.get('name', '')})",
                            tier_data.get('code', ''),
                            f"{course_data.get('description', '')} {tier_data.get('includes', '')}"
                        ))

            await db.commit()
            logger.info("Courses loaded successfully from JSON")
            
        except Exception as e:
            logger.error(f"Error loading courses: {str(e)}")
            raise

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


# Добавляем функцию get_course_name перед get_user_info
async def get_course_name(course_id: str) -> str:
    """Получение названия курса по его ID"""
    try:
        result = await safe_db_operation('''
            SELECT name FROM courses 
            WHERE id = ?
        ''', (course_id,))
        
        if result and len(result) > 0:
            return result[0][0]  # Первый столбец первой строки
        return "Неизвестный курс"
    except Exception as e:
        logger.error(f"Ошибка при получении названия курса: {e}")
        return "Неизвестный курс"

@cache_with_timeout(300)  # Кэш на 5 минут
async def get_user_info(user_id: int) -> str:
    """Получение информации о пользователе и его курсе"""
    logger.debug(f"Получение информации о пользователе {user_id}")
    try:
        # Получаем данные пользователя и курса
        user_data = await safe_db_operation('''
                SELECT u.name, uc.course_id, uc.current_lesson, uc.version_id, uc.first_lesson_time
                FROM users u
                LEFT JOIN user_courses uc ON u.user_id = uc.user_id
                WHERE u.user_id = ?
            ''', (user_id,))
        
        # Проверяем, что данные получены
        if not user_data or len(user_data) == 0:
            return "❌ Данные пользователя не найдены"
            
        # Берем первую запись (может быть несколько курсов)
        user_info = user_data[0]
        
        # Проверяем, что у пользователя есть курс
        if len(user_info) < MIN_USER_FIELDS or not user_info[1]:
            return f"👋 Привет, {user_info[0]}!\n\nУ вас пока нет активных курсов."
            
        # Получаем данные о курсе
        name, course_id, lesson, version_id, first_lesson = user_info
        
        # Форматируем дату начала курса
        try:
            first_lesson_dt = datetime.fromisoformat(first_lesson.replace('Z', '+00:00'))
            first_lesson_formatted = first_lesson_dt.strftime("%d.%m.%Y")
        except (ValueError, AttributeError):
            first_lesson_formatted = "неизвестно"
            
        # Получаем название курса
        course_name = await get_course_name(course_id)
        
        # Формируем информацию о пользователе
        return (
            f"👋 Привет, {name}!\n\n"
            f"🎓 Курс: {course_name}\n"
            f"📚 Текущий урок: {lesson}\n"
            f"🗓 Начало курса: {first_lesson_formatted}\n"
            f"🔑 Тариф: {version_id}"
        )
        
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
        logger.error(f"Ошибка очистки scheduled_files: {e}")


    