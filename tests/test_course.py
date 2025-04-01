import pytest
from unittest.mock import AsyncMock, patch
from aiogram.types import Message
from src.handlers.course import handle_start

@pytest.mark.asyncio
async def test_handle_start(message_mock):
    """Тестируем обработчик /start 🚀"""
    # Настраиваем мок для get_user_info
    mock_user_info = AsyncMock()
    mock_user_info.return_value = {
        'name': 'Тест Тестович',
        'course_id': 'python101',
        'current_lesson': 1
    }
    
    # Настраиваем мок для safe_db_operation
    mock_db = AsyncMock()
    mock_db.return_value = []  # Возвращаем пустой список для scheduled_files
    
    with patch('src.handlers.course.get_user_info', new=mock_user_info), \
         patch('src.utils.scheduler.safe_db_operation', return_value=mock_db):
        
        await handle_start(message_mock)
        message_mock.answer.assert_called_with("Привет, Тест Тестович! 👋")

@pytest.mark.asyncio
async def test_handle_course_start(message_mock, bot):
    """Тестируем начало курса 📚"""
    message_mock.bot = bot
    
    # Настраиваем мок для get_user_info
    mock_user_info = AsyncMock()
    mock_user_info.return_value = {
        'name': 'Тест Тестович',
        'course_id': 'python101',
        'current_lesson': 1,
        'status': 'active'
    }
    
    # Настраиваем мок для safe_db_operation
    mock_db = AsyncMock()
    mock_db.return_value = []
    
    with patch('src.handlers.course.get_user_info', new=mock_user_info), \
         patch('src.utils.scheduler.safe_db_operation', return_value=mock_db), \
         patch('src.keyboards.user.get_main_keyboard', return_value=None):  # Исправили путь к клавиатуре
        
        await handle_start(message_mock)
        message_mock.answer.assert_called_once()