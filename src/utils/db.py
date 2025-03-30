import json
import aiosqlite
import os
import logging

from src.utils.courses import verify_code
from src.config import ADMIN_GROUP_ID, get_lesson_delay
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
DB_PATH = "data/bot.db"

async def init_db():
    logger.info("Initializing database...")
    os.makedirs('data', exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS user_courses (
                user_id INTEGER,
                course_id TEXT NOT NULL,
                version_id TEXT NOT NULL DEFAULT 'basic',
                current_lesson INTEGER DEFAULT 1,
                activation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                PRIMARY KEY(user_id, course_id, version_id)
            );
            
            CREATE TABLE IF NOT EXISTS homeworks (
                hw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id),
                course_id TEXT NOT NULL,
                lesson INTEGER,
                status TEXT CHECK(status IN ('pending', 'approved', 'declined')),
                submission_time DATETIME,
                approval_time DATETIME,
                next_lesson_at DATETIME,
                admin_comment TEXT,
                file_id TEXT,  -- Remove NOT NULL constraint
                admin_id INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER,
                current_state TEXT,
                current_course TEXT,
                current_lesson INTEGER,
                PRIMARY KEY(user_id)
            );
        ''')
        
        # Add next_lesson_at column if it doesn't exist
        try:
            await db.execute('ALTER TABLE homeworks ADD COLUMN next_lesson_at DATETIME')
        except:
            pass  # Column might already exist
            
        await db.commit()
        logger.info("Database initialization completed")

async def set_course_state(user_id: int, course_id: str, state: str, lesson: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_states 
            (user_id, current_state, current_course, current_lesson)
            VALUES (?, ?, ?, ?)
        ''', (user_id, state, course_id, lesson or 1))
        
        if state == 'waiting_next_lesson':
            await db.execute('''
                UPDATE user_courses
                SET current_lesson = ?
                WHERE user_id = ? AND course_id = ?
            ''', (lesson, user_id, course_id))
        
        await db.commit()
        logger.info(f"5002 | Состояние курса: {user_id=} {course_id=} {state=} {lesson=}")

async def get_active_courses_states(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT s.course_id, s.current_state, s.current_lesson, c.current_lesson
            FROM user_states s
            JOIN user_courses c 
            ON s.user_id = c.user_id AND s.course_id = c.course_id
            WHERE s.user_id = ?
        ''', (user_id,))
        return await cursor.fetchall()

async def submit_homework(user_id: int, course_id: str, lesson: int, file_id: str, bot: Bot = None):
    """Submit homework and notify admins"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Verify course enrollment
            cursor = await db.execute('''
                SELECT uc.version_id, u.name
                FROM user_courses uc
                JOIN users u ON u.user_id = uc.user_id
                WHERE uc.user_id = ? AND uc.course_id = ?
            ''', (user_id, course_id))
            course_data = await cursor.fetchone()
            
            if not course_data:
                logger.error(f"6001 | Курс не найден: {user_id=} {course_id=}")
                return False
                
            version_id, user_name = course_data
            
            # Begin transaction manually
            await db.execute('BEGIN TRANSACTION')
            try:
                # Record homework submission
                await db.execute('''
                    INSERT INTO homeworks 
                    (user_id, course_id, lesson, status, submission_time, file_id) 
                    VALUES (?, ?, ?, 'pending', datetime('now'), ?)
                ''', (user_id, course_id, lesson, file_id))
                
                # Update user state if needed
                await db.execute('''
                    UPDATE user_states 
                    SET current_state = 'waiting_approval'
                    WHERE user_id = ? AND current_course = ?
                ''', (user_id, course_id))
                
                await db.commit()
                logger.info(f"3002 | Домашка по курсу: {user_id=} {course_id=} {lesson=}")
                
                # Rest of the code (admin notification) stays the same...
                
            except Exception as e:
                await db.execute('ROLLBACK')
                raise e

            # Notify admin group if bot instance is provided
            if bot and ADMIN_GROUP_ID:
                try:
                    # Create inline keyboard for admin actions
                    markup = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="✅ Принять", callback_data=f"hw_approve_{user_id}_{course_id}_{lesson}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hw_reject_{user_id}_{course_id}_{lesson}")
                    ]])
                    
                    # First try to send photo directly
                    try:
                        await bot.send_photo(
                            chat_id=ADMIN_GROUP_ID,
                            photo=file_id,
                            caption=f"📚 Новая домашняя работа!\n\n"
                                   f"👤 Ученик: {user_name}\n"
                                   f"📝 Курс: {course_id}\n"
                                   f"📊 Тариф: {version_id}\n"
                                   f"📖 Урок: {lesson}\n"
                                   f"🆔 ID: {user_id}",
                            reply_markup=markup
                        )
                        logger.info(f"3003 | Домашка отправлена админам: {ADMIN_GROUP_ID=} {user_id=} {course_id=} {lesson=}")
                        return True
                    except Exception as e:
                        logger.error(f"3006 | Ошибка отправки фото: {e}")
                        # If sending photo fails, try forwarding the message
                        try:
                            await bot.forward_message(
                                chat_id=ADMIN_GROUP_ID,
                                from_chat_id=user_id,
                                message_id=int(file_id)
                            )
                            # Send additional info message
                            await bot.send_message(
                                ADMIN_GROUP_ID,
                                f"📚 Новая домашняя работа!\n\n"
                                f"👤 Ученик: {user_name}\n"
                                f"📝 Курс: {course_id}\n"
                                f"📊 Тариф: {version_id}\n"
                                f"📖 Урок: {lesson}\n"
                                f"🆔 ID: {user_id}",
                                reply_markup=markup
                            )
                            logger.info(f"3003 | Домашка переслана админам: {ADMIN_GROUP_ID=} {user_id=} {course_id=} {lesson=}")
                            return True
                        except Exception as e:
                            logger.error(f"3007 | Ошибка пересылки сообщения: {e}")
                            return False
                except Exception as e:
                    logger.error(f"3005 | Ошибка отправки в админскую группу: {e}")
                    return False
            
            return True
            
    except Exception as e:
        logger.error(f"Error in submit_homework: {e}", exc_info=True)
        return False

async def verify_course_code(code: str, user_id: int) -> tuple[bool, str]:
    """Verify course code and return (success, course_id)"""
    try:
        with open('data/courses.json', 'r', encoding='utf-8') as f:
            courses = json.load(f)
            
        for course_id, course in courses.items():
            for version in course['versions']:
                if version['code'] == code:
                    async with aiosqlite.connect(DB_PATH) as db:
                        cursor = await db.execute('''
                            SELECT 1 FROM user_courses 
                            WHERE user_id = ? AND course_id = ?
                        ''', (user_id, course_id))
                        
                        if await cursor.fetchone():
                            logger.warning(f"User {user_id} already enrolled in course {course_id}")
                            return False, None
                        
                        # Begin transaction manually
                        await db.execute('BEGIN TRANSACTION')
                        try:
                            # Activate course for user
                            await db.execute('''
                                INSERT INTO user_courses (user_id, course_id, version_id, current_lesson)
                                VALUES (?, ?, ?, 1)
                            ''', (user_id, course_id, version['id']))
                            
                            # Set initial user state
                            await db.execute('''
                                INSERT OR REPLACE INTO user_states 
                                (user_id, current_state, current_course, current_lesson)
                                VALUES (?, 'active', ?, 1)
                            ''', (user_id, course_id))
                            
                            await db.commit()
                            logger.info(f"Enrolled user {user_id} in course {course_id}:{version['id']}")
                            return True, course_id
                            
                        except Exception as e:
                            await db.execute('ROLLBACK')
                            raise e
                        
        logger.warning(f"Invalid course code: {code}")
        return False, None
        
    except Exception as e:
        logger.error(f"Error in verify_course_code: {e}", exc_info=True)
        return False, None

async def update_tokens(user_id: int, amount: int, reason: str) -> bool:
    """Update user tokens with manual transaction handling"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN TRANSACTION')
            try:
                # Get current tokens
                cursor = await db.execute('SELECT tokens FROM users WHERE user_id = ?', (user_id,))
                result = await cursor.fetchone()
                current_tokens = result[0] if result else 0
                
                # Update tokens
                await db.execute('''
                    UPDATE users 
                    SET tokens = tokens + ? 
                    WHERE user_id = ?
                ''', (amount, user_id))
                
                # Log transaction
                await db.execute('''
                    INSERT INTO token_history (user_id, amount, reason, timestamp)
                    VALUES (?, ?, ?, datetime('now'))
                ''', (user_id, amount, reason))
                
                await db.commit()
                logger.info(f"8001 | Токены обновлены: {user_id=} {amount=} {reason=}")
                return True
                
            except Exception as e:
                await db.execute('ROLLBACK')
                logger.error(f"8002 | Ошибка обновления токенов: {e}")
                return False
                
    except Exception as e:
        logger.error(f"8003 | Критическая ошибка обновления токенов: {e}")
        return False

async def set_user_state(user_id: int, state: str, course_id: str = None, lesson: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''
            INSERT OR REPLACE INTO user_states 
            (user_id, current_state, current_course, current_lesson)
            VALUES (?, ?, ?, ?)
            ''',
            (user_id, state, course_id, lesson)
        )
        await db.commit()
        logger.info(f"5001 | Обновление состояния: {user_id=}, {state=}")

async def get_user_state(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            '''
            SELECT current_state, current_course, current_lesson 
            FROM user_states WHERE user_id = ?
            ''',
            (user_id,)
        )
        return await cursor.fetchone()


async def add_user(user_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, name, registration_date)
            VALUES (?, ?, datetime('now'))
        ''', (user_id, name))
        await db.commit()

async def get_user(user_id: int):
    """Get user data from database"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT * FROM users WHERE user_id = ?',
            (user_id,)
        )
        return await cursor.fetchone()

async def get_user_info(user_id: int) -> str:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # First get basic user info
            cursor = await db.execute('''
                SELECT 
                    u.name,
                    uc.course_id,
                    uc.version_id,
                    uc.current_lesson
                FROM users u
                LEFT JOIN user_courses uc ON u.user_id = uc.user_id
                WHERE u.user_id = ?
            ''', (user_id,))
            user_data = await cursor.fetchone()
            
            if not user_data:
                return "User not found"
                
            name, course_id, version_id, lesson = user_data
            
            if not course_id:
                return f"👤 {name}\n📚 Курс не активирован"
                
            # Get course info
            with open('data/courses.json', 'r', encoding='utf-8') as f:
                courses = json.load(f)
            course = courses.get(course_id, {})
            version = next((v for v in course.get('versions', []) if v['id'] == version_id), {})
            
            # Get homework status
            cursor = await db.execute('''
                SELECT status, submission_time, next_lesson_at
                FROM homeworks 
                WHERE user_id = ? AND course_id = ? AND lesson = ?
                ORDER BY submission_time DESC LIMIT 1
            ''', (user_id, course_id, lesson))
            hw_data = await cursor.fetchone()
            
            status_msg = "⏳ Ожидаю отправку материалов урока"
            if hw_data:
                hw_status, sent_at, next_lesson = hw_data
                if hw_status == 'pending':
                    status_msg = "💌 Домашка на проверке"
                elif hw_status == 'approved' and next_lesson:
                    from datetime import datetime
                    next_time = datetime.fromisoformat(next_lesson)
                    if datetime.now() < next_time:
                        time_left = next_time - datetime.now()
                        days = time_left.days
                        hours = time_left.seconds // 3600
                        minutes = (time_left.seconds % 3600) // 60
                        
                        if days > 0:
                            status_msg = f"⏳ Следующий урок через {days}д {hours}ч"
                        elif hours > 0:
                            status_msg = f"⏳ Следующий урок через {hours}ч {minutes}м"
                        else:
                            status_msg = f"⏳ Следующий урок через {minutes}м"
                    else:
                        status_msg = "✅ Можно начинать следующий урок"
                elif hw_status == 'declined':
                    status_msg = "❌ Домашка отклонена"
            
            return (f"👤 {name}\n"
                    f"📚 Курс: {course.get('name', 'Неизвестный курс')}\n"
                    f"📊 Тариф: {version.get('name', 'Базовый')}\n"
                    f"📝 Урок: {lesson}\n"
                    f"{status_msg}")
                    
    except Exception as e:
        logger.error(f"Error in get_user_info: {e}")
        return "Error getting user info"

async def optimize_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE INDEX IF NOT EXISTS idx_user_courses_user 
            ON user_courses(user_id);
            
            CREATE INDEX IF NOT EXISTS idx_homeworks_user 
            ON homeworks(user_id, course_id);
            
            CREATE INDEX IF NOT EXISTS idx_user_states_user 
            ON user_states(user_id);
        ''')
        await db.commit()


async def test_admin_group(bot: Bot) -> bool:
    """Test bot permissions and communication with admin group"""
    try:
        if not ADMIN_GROUP_ID:
            logger.error("1001 | ADMIN_GROUP_ID не настроен")
            return False

        # Convert group ID to int if it's a string
        group_id = int(ADMIN_GROUP_ID) if isinstance(ADMIN_GROUP_ID, str) else ADMIN_GROUP_ID
        
        # Check if bot is member of the group
        try:
            chat = await bot.get_chat(group_id)
            logger.info(f"1002 | Подключен к группе: {chat.title} (ID: {group_id})")
        except Exception as e:
            logger.error(f"1003 | Бот не может получить доступ к группе {group_id}")
            logger.error(f"1003a | Проверьте: \n"
                        f"1. ID группы правильный\n"
                        f"2. Бот добавлен в группу\n"
                        f"3. Группа публичная или бот имеет доступ\n"
                        f"Ошибка: {str(e)}")
            return False

        # Check bot permissions
        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                logger.error(f"1004 | Бот не является администратором в группе {group_id}")
                return False
            logger.info(f"1004a | Бот имеет права администратора в группе (статус: {bot_member.status})")
        except Exception as e:
            logger.error(f"1004b | Ошибка проверки прав бота: {e}")
            return False
        
        # Send test message with button
        try:
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Проверка связи", callback_data="admin_test")
            ]])
            
            msg = await bot.send_message(
                group_id,
                "🤖 Бот запущен и готов к работе!\n"
                "Нажмите кнопку для подтверждения связи.",
                reply_markup=markup
            )
            
            logger.info("1005 | Тестовое сообщение отправлено в группу админов")
            return True
        except Exception as e:
            logger.error(f"1005a | Ошибка отправки тестового сообщения: {e}")
            return False

    except Exception as e:
        logger.error(f"1006 | Ошибка проверки админской группы: {e}")
        return False


async def handle_homework_approval(user_id: int, course_id: str, lesson: int, status: str, admin_id: int, comment: str = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN TRANSACTION')
            try:
                await db.execute(f'''
                    UPDATE homeworks 
                    SET status = ?, 
                        approval_time = datetime('now'),
                        next_lesson_at = datetime('now', ?),
                        admin_id = ?,
                        admin_comment = ?
                    WHERE user_id = ? 
                        AND course_id = ? 
                        AND lesson = ?
                        AND status = 'pending'
                ''', (status, get_lesson_delay(), admin_id, comment, user_id, course_id, lesson))
                
                if status == 'approved':
                    # Set next lesson availability time (24 hours from now)
                    await db.execute('''
                        UPDATE homeworks
                        SET next_lesson_at = datetime('now', '+24 hours')
                        WHERE user_id = ? AND course_id = ? AND lesson = ?
                    ''', (user_id, course_id, lesson))
                    
                    # Update user state
                    await db.execute('''
                        UPDATE user_states
                        SET current_state = 'waiting_next_lesson'
                        WHERE user_id = ? AND current_course = ?
                    ''', (user_id, course_id))
                else:
                    # If rejected, set state back to waiting_homework
                    await db.execute('''
                        UPDATE user_states
                        SET current_state = 'waiting_homework'
                        WHERE user_id = ? AND current_course = ?
                    ''', (user_id, course_id))
                
                await db.commit()
                logger.info(f"7001 | Домашка {status}: {user_id=} {course_id=} {lesson=}")
                return True
                
            except Exception as e:
                await db.execute('ROLLBACK')
                logger.error(f"7002 | Ошибка обработки домашки: {e}")
                return False
                
    except Exception as e:
        logger.error(f"7003 | Критическая ошибка обработки домашки: {e}")
        return False
    