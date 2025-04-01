import os
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from src.utils.db import init_db, DB_PATH


@pytest_asyncio.fixture(scope="function")
def event_loop():
    """Создаём луп для тестов (и немного магии ✨)"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Инициализируем чистую базу данных для каждого теста 🗃️"""
    # Удаляем старую БД, если она есть
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    # Создаём новую чистую БД
    await init_db()
    yield
    
    # Чистим за собой после теста
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest_asyncio.fixture
async def storage():
    """Хранилище состояний (чтобы боту было где хранить свои мысли 🤔)"""
    return MemoryStorage()

@pytest_asyncio.fixture
async def bot():
    """Создаём мок-бота (почти настоящий, только не кусается 🤖)"""
    bot = AsyncMock(Bot)
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_video = AsyncMock()
    return bot

@pytest_asyncio.fixture
async def dp(storage):
    """Диспетчер (главный по распределению сообщений 📮)"""
    dp = Dispatcher(storage=storage)
    return dp

def pytest_configure(config):
    """Настраиваем pytest-asyncio (чтобы не ругался 🤫)"""
    # Регистрируем маркер для асинхронных тестов
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async test"
    )
    
    # Настраиваем режим asyncio
    config.option.asyncio_mode = "strict"


import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def message_mock():
    """Фикстура для сообщений (теперь точно работает! 📨)"""
    message = AsyncMock()
    # Настраиваем from_user
    message.from_user = AsyncMock()
    message.from_user.id = 123
    message.from_user.first_name = "Тест"
    
    # Важно! Делаем return_value для асинхронных методов
    message.answer.return_value = None  # или что там должно вернуться
    message.reply.return_value = None
    
    # Настраиваем бота
    message.bot = AsyncMock()
    message.bot.send_message.return_value = None
    
    return message

@pytest.fixture
def mock_user_info():
    """Фикстура для get_user_info (потому что он у нас капризный 👻)"""
    mock = AsyncMock()
    mock.return_value = {
        'name': 'Тест Тестович',
        'course_id': 'python101',
        'status': 'active'
    }
    return mock

@pytest.fixture
def callback_mock():
    """Фикстура для callback (с начинкой! 🎯)"""
    callback = AsyncMock()
    callback.from_user = AsyncMock()
    callback.from_user.id = 999
    callback.message = AsyncMock()
    callback.message.from_user = AsyncMock()
    callback.message.from_user.id = 123
    callback.answer = AsyncMock()
    callback.data = "test_callback_data"
    callback.bot = AsyncMock()
    return callback

@pytest.fixture
def state_mock():
    """Фикстура для состояний (FSM) 🔄"""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.set_data = AsyncMock()
    state.finish = AsyncMock()
    return state
    