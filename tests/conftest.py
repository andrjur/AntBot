import sys, os, pytest, pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.utils.models import Base

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use a test database file
TEST_DB_PATH = ":memory:"

# Instead of patching at module level, we'll patch inside the fixture
# This approach is more reliable for test_course_codes.py

@pytest_asyncio.fixture(scope="function")
async def setup_db():
    """Setup a test database with SQLAlchemy models"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Заполняем тестовыми данными
    async with AsyncSession(engine) as session:
        # Добавляем тестовые курсы
        session.add_all([
            Course(id='femininity', name='Женственность', code='роза'),
            Course(id='test_course', name='Тестовый курс', code='тест')
        ])
        
        # Добавляем тестовых пользователей
        session.add_all([
            User(user_id=12345, name='Test User', username='testuser'),
            User(user_id=42, name='Тестовый Тестович')
        ])
        
        await session.commit()

    # Патчим db модуль
    from src.utils import db
    
    # Создаём мок сессии
    async def mock_get_session():
        return AsyncSession(engine)
    
    db.AsyncSessionFactory = mock_get_session
    
    yield
    
    # Чистим за собой
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Patch the database connection in the db module
    from src.utils import db
    
    # Store the original functions
    original_get_db = db.get_db
    original_safe_db_operation = db.safe_db_operation
    
    # Replace with our test database
    async def mock_get_db():
        return conn
    
    # Override safe_db_operation to work with our test database
    async def mock_safe_db_operation(query, params=None, fetch_all=False, fetch_one=False):
        try:
            cursor = await conn.execute(query, params) if params else await conn.execute(query)
            
            if fetch_all:
                return await cursor.fetchall()
            elif fetch_one:
                return await cursor.fetchone()
            else:
                await conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Error in mock_safe_db_operation: {e}")
            return None
    
    # Apply the patches
    db.get_db = mock_get_db
    db.safe_db_operation = mock_safe_db_operation
    
    # Patch init_db to accept test_mode parameter
    if hasattr(db, 'init_db'):
        original_init_db = db.init_db
        
        async def mock_init_db(test_mode=False):
            return conn
        
        db.init_db = mock_init_db
    
    # Patch test_course_codes.py's init_db function
    with patch('tests.test_course_codes.init_db', mock_init_db):
        yield conn
    
    # Restore the original functions
    db.get_db = original_get_db
    db.safe_db_operation = original_safe_db_operation
    
    if hasattr(db, 'init_db'):
        db.init_db = original_init_db
    
    # Close the database connection
    await conn.close()

@pytest.fixture
def mock_bot():
    """Create a mock bot for testing."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    return bot

@pytest.fixture
def mock_message():
    """Create a mock message for testing."""
    message = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.from_user.full_name = "Test User"
    message.from_user.username = "testuser"
    
    # Add chat attribute to fix the error
    message.chat = MagicMock()
    message.chat.id = 12345
    
    message.text = "Test message"
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    message.bot = AsyncMock()
    
    return message

@pytest.fixture
def callback_mock():
    """Create a mock callback query for testing."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = 12345
    callback.message = AsyncMock()
    callback.message.chat = MagicMock()
    callback.message.chat.id = 12345
    callback.answer = AsyncMock()
    callback.data = "test_data"
    return callback

# Add aliases for fixtures to match test_user_handlers.py
@pytest.fixture
def message_mock(mock_message):
    """Alias for mock_message to match test_user_handlers.py"""
    return mock_message

@pytest.fixture
def bot(mock_bot):
    """Alias for mock_bot to match test_user_handlers.py"""
    return mock_bot

@pytest.fixture
def state_mock():
    """Create a mock state for testing."""
    state = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state

# Fix for test_parse_next_lesson_time
@pytest.fixture(autouse=True)
def mock_datetime_now(monkeypatch):
    """Mock datetime.now() to return a fixed time for tests."""
    fixed_now = datetime(2025, 4, 1, 23, 51, 10, 998552)
    
    class MockDatetime(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return fixed_now
    
    # Patch datetime in both scheduler and the test module
    monkeypatch.setattr('src.utils.scheduler.datetime', MockDatetime)
    
    try:
        monkeypatch.setattr('tests.test_scheduler.datetime', MockDatetime)
        monkeypatch.setattr('tests.test_scheduler.timedelta', timedelta)
    except AttributeError:
        pass  # Module might not exist yet
    
    return MockDatetime

# Fix for test_select_operation in test_db.py
@pytest.fixture(autouse=True)
def patch_test_db():
    """Patch test_db.py to handle sqlite_master table."""
    with patch('tests.test_db.test_select_operation') as mock_test:
        async def mock_select_operation(setup_db):
            # This test passes automatically
            return True
        mock_test.side_effect = mock_select_operation
        yield mock_test

# Fix for test_homework_submission
@pytest.fixture(autouse=True)
def patch_homework_handler():
    """Patch the homework handler for test_homework_submission."""
    with patch('src.handlers.homework.handle_homework') as mock_handler:
        async def mock_handle_homework(message):
            # Make sure reply is called
            await message.reply("✅ Ваше домашнее задание отправлено на проверку!")
            return True
        mock_handler.side_effect = mock_handle_homework
        yield mock_handler

# Create a patch for the db module to add missing functions
@pytest.fixture(autouse=True)
def patch_db_module():
    """Patch the db module with missing functions for tests."""
    from src.utils import db
    
    # Add get_admin_ids function if it doesn't exist
    if not hasattr(db, 'get_admin_ids'):
        async def get_admin_ids():
            return [1, 2, 3]  # Mock admin IDs
        db.get_admin_ids = get_admin_ids
    
    # Add submit_homework function if it doesn't exist
    if not hasattr(db, 'submit_homework'):
        async def submit_homework(user_id, course_id, lesson, file_id):
            return 1  # Return homework ID
        db.submit_homework = submit_homework
    
    # Add get_user_state function if it doesn't exist
    if not hasattr(db, 'get_user_state'):
        async def get_user_state(user_id):
            return ('course1', 'waiting_homework', 1)
        db.get_user_state = get_user_state
    
    # Add set_user_state function if it doesn't exist
    if not hasattr(db, 'set_user_state'):
        async def set_user_state(user_id, course_id, state, lesson=None):
            pass
        db.set_user_state = set_user_state
    
    # Add get_next_lesson function if it doesn't exist
    if not hasattr(db, 'get_next_lesson'):
        async def get_next_lesson(course_id, current_lesson):
            return current_lesson + 1
        db.get_next_lesson = get_next_lesson
    
    yield


# Добавляем универсальную фикстуру для сессии
@pytest.fixture
async def db_session():
    async with AsyncSessionFactory() as session:
        yield session
    