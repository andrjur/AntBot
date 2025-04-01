import pytest
from src.handlers.user import start_handler, process_registration, process_activation, handle_photo
from src.utils.db import get_user, get_user_info, submit_homework
from aiogram.types import Message, User
from aiogram.fsm.context import FSMContext
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_registration_flow():
    message = AsyncMock(spec=Message)
    message.text = "Тестовый Тестович"
    message.from_user = AsyncMock(id=123)
    message.answer = AsyncMock()
    
    state = AsyncMock(FSMContext)
    
    with patch('src.handlers.user.add_user', new=AsyncMock()) as mock_add_user, \
         patch('src.utils.db.get_user', new=AsyncMock(return_value=(123, "Тестовый Тестович", "2024-01-01"))):
        
        await process_registration(message, state)
        mock_add_user.assert_awaited_once_with(123, "Тестовый Тестович")
        
        # Move assertions inside the context manager
        user = await get_user(123)
        assert user is not None
        assert user[1] == "Тестовый Тестович"
    
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_course_activation():
    message = AsyncMock(spec=Message)
    message.from_user = AsyncMock(id=12345)  # <-- Сначала создаем from_user
    message.text = "роза"
    message.answer = AsyncMock()
    
    state = AsyncMock(FSMContext)
    
    with patch('src.handlers.user.verify_course_code', 
              new=AsyncMock(return_value=(1, "Тестовый курс"))), \
         patch('src.handlers.user.safe_db_operation', new=AsyncMock()):
        
        await process_activation(message, state)
        message.answer.assert_awaited_once()

@pytest.mark.asyncio
async def test_homework_submission():
    """Тестируем отправку домашки 📚"""
    # Создаем мок сообщения с фото
    message = AsyncMock(spec=Message)
    message.from_user = AsyncMock(id=12345)  # Correctly mock from_user
    message.photo = [MagicMock(file_id="test_photo")]
    message.bot = AsyncMock()
    message.reply = AsyncMock()
    
    # Патчим функции для тестирования
    with patch('src.handlers.user.get_user_state', return_value=('course1', 'waiting_homework', 1)), \
         patch('src.handlers.user.submit_homework', return_value=True), \
         patch('src.handlers.user.set_user_state') as mock_set_state:
        
        # Вызываем тестируемую функцию
        await handle_photo(message)
        
        # Проверяем результаты
        message.reply.assert_called_once_with("✅ Домашняя работа отправлена на проверку!")
        mock_set_state.assert_called_once()