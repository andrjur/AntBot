import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from src.utils.db import init_db

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def storage():
    return MemoryStorage()

@pytest.fixture
async def bot():
    bot = AsyncMock(Bot)
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_video = AsyncMock()
    return bot

@pytest.fixture
async def dp(storage):
    dp = Dispatcher(storage=storage)
    return dp

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()