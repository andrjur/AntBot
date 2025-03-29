import aiosqlite
import os
import logging

logger = logging.getLogger(__name__)
DB_PATH = "data/bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_courses (
                user_id INTEGER,
                course_id TEXT NOT NULL,
                current_lesson INTEGER DEFAULT 1,
                activation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                PRIMARY KEY(user_id, course_id)
            )
        ''')
        
        await db.commit()
    logger.info("Initializing database...")
    os.makedirs('data', exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # First, check if the column exists
        cursor = await db.execute('''
            SELECT name FROM pragma_table_info('user_courses') 
            WHERE name='current_lesson'
        ''')
        column_exists = await cursor.fetchone()
        
        # Create base tables
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                registration_date DATETIME,
                birthday DATE,
                referral_count INTEGER DEFAULT 0
            )
        ''')
        
        # Create Courses table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                course_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code_word TEXT NOT NULL,
                price_rub INTEGER,
                price_tokens INTEGER,
                type TEXT CHECK(type IN ('main', 'auxiliary')),
                description TEXT
            )
        ''')
        
        # Create User Courses table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_courses (
                user_id INTEGER REFERENCES users(user_id),
                course_id TEXT REFERENCES courses(course_id),
                tariff TEXT CHECK(tariff IN ('premium', 'self_check')),
                progress INTEGER DEFAULT 0,
                activated_at DATETIME,
                PRIMARY KEY (user_id, course_id)
            )
        ''')
        
        # Create Homeworks table
        # In init_db() homeworks table update
        await db.execute('''
            CREATE TABLE IF NOT EXISTS homeworks (
                hw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id),
                course_id TEXT REFERENCES courses(course_id),
                lesson INTEGER,
                status TEXT CHECK(status IN ('pending', 'approved', 'declined')),
                submission_time DATETIME,
                approval_time DATETIME,
                admin_comment TEXT,
                file_id TEXT NOT NULL,
                admin_id INTEGER
            )
        ''')
        
        # Add new table for user states
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER NOT NULL,
                course_id TEXT NOT NULL,
                current_state TEXT CHECK(current_state IN (
                    'awaiting_homework', 'lesson_completed', 
                    'waiting_next_lesson', 'course_completed'
                )),
                current_lesson INTEGER DEFAULT 1,
                last_action DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, course_id),
                FOREIGN KEY (course_id) REFERENCES courses(course_id)
            )
        ''')
        
        # Add progress tracking to user_courses
        # Only add the column if it doesn't exist
        if not column_exists:
            try:
                await db.execute('''
                    ALTER TABLE user_courses
                    ADD COLUMN current_lesson INTEGER DEFAULT 1
                ''')
                logger.info("Added current_lesson column to user_courses")
            except Exception as e:
                logger.warning(f"Could not add current_lesson column: {e}")
        
        await db.commit()
        logger.info("Database initialization completed")

async def set_course_state(user_id: int, course_id: str, state: str, lesson: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_states 
            (user_id, course_id, current_state, current_lesson)
            VALUES (?, ?, ?, ?)
        ''', (user_id, course_id, state, lesson or 1))
        
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

async def submit_homework(user_id: int, course_id: str, lesson: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Verify course enrollment
        cursor = await db.execute('''
            SELECT 1 FROM user_courses 
            WHERE user_id = ? AND course_id = ?
        ''', (user_id, course_id))
        if not await cursor.fetchone():
            logger.error(f"6001 | Курс не найден: {user_id=} {course_id=}")
            return False
        
        await db.execute('''
            INSERT INTO homeworks (...) 
            VALUES (?, ?, ?, 'pending', datetime('now'), ?)
        ''', (user_id, course_id, lesson, file_id))
        await db.commit()
        logger.info(f"3002 | Домашка по курсу: {user_id=} {course_id=} {lesson=}")
        return True

async def update_tokens(user_id: int, amount: int, reason: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Atomic transaction
        async with db.transaction():
            # Update balance
            await db.execute('''
                UPDATE user_tokens 
                SET tokens = tokens + ? 
                WHERE user_id = ?
            ''', (amount, user_id))
            
            # Record transaction
            await db.execute('''
                INSERT INTO transactions 
                (user_id, amount, reason)
                VALUES (?, ?, ?)
            ''', (user_id, amount, reason))
            
            # Check for achievement unlocks
            if reason == 'homework_approval':
                await check_achievements(user_id)
        await db.commit()
        logger.info(f"4001 | Обновление токенов: {user_id=}, {amount=}, {reason=}")

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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
        user_data = await cursor.fetchone()
        
        if not user_data:
            return "👤 Профиль не найден"
        
        name = user_data[0]
        
        cursor = await db.execute('''
            SELECT course_id, current_lesson 
            FROM user_courses 
            WHERE user_id = ?
        ''', (user_id,))
        course_data = await cursor.fetchone()
        
    if course_data:
        course_id, lesson = course_data
        with open('data/courses.json', 'r', encoding='utf-8') as f:
            courses = json.load(f)
        course = courses.get(course_id, {})
        
        return (f"👤 {name}\n"
                f"📚 Курс: {course.get('name', 'Не активирован')}\n"
                f"📝 Текущий урок: {lesson or 1}")
    else:
        return f"👤 {name}\n📚 Курс не активирован"
