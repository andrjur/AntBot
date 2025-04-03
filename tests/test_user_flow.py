import pytest
from src.handlers.user import start_handler, process_registration, process_activation, handle_photo
# Change from:
# from src.utils.db import get_user_info
# To:
from src.utils.requests import get_user_info
from aiogram.types import Message, User
from aiogram.fsm.context import FSMContext
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message
from conftest import db_session  # Используем общую фикстуру

@pytest.mark.asyncio
async def test_registration_flow(db_session):  # Теперь используем общую сессию
    message = AsyncMock(spec=Message)
    message.text = "Тестовый Тестович"
    message.from_user = AsyncMock(id=123)
    message.answer = AsyncMock()
    
    state = AsyncMock(FSMContext)
    
    mock_user_data = (123, "Тестовый Тестович", "2024-01-01", 0)
    
    # Меняем адрес патча на локальный импорт 🗺️
    with patch('src.handlers.user.add_user', new=AsyncMock(return_value=True)) as mock_add_user, \
         patch('tests.test_user_flow.get_user', new=AsyncMock(return_value=mock_user_data)) as mock_get_user:
        
        await process_registration(message, state)
        
        mock_add_user.assert_awaited_once_with(123, "Тестовый Тестович")
        
        # Теперь достаём данные из правильного мока 🥟
        user = await get_user(123)
        assert user == mock_user_data
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
async def test_homework_submission(mock_message):
    """Тестируем отправку домашки 📚"""
    # Настраиваем мок сообщения
    mock_message.photo = [MagicMock(file_id="test_photo")]
    mock_message.document = None
    
    # Импортируем модуль здесь, чтобы патчи применились правильно
    import src.handlers.homework
    
    # Патчим функции для тестирования
    with patch('src.utils.db.get_user_state', return_value=('course1', 'waiting_homework', 1)), \
         patch('src.utils.db.submit_homework', return_value=1), \
         patch('src.utils.db.set_user_state') as mock_set_state, \
         patch('src.utils.db.get_admin_ids', return_value=[1, 2]), \
         patch('src.keyboards.markup.create_main_menu') as mock_create_menu:
        
        # Вызываем тестируемую функцию
        await src.handlers.homework.handle_homework(mock_message)
        
        # Проверяем результаты
        mock_message.reply.assert_called_once()
        assert "отправлено на проверку" in mock_message.reply.call_args[0][0]
        
        # Проверяем, что состояние пользователя было обновлено
        mock_set_state.assert_called_once()
        
        # Проверяем, что было показано основное меню
        mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_error_handling():
    """Тестируем обработку ошибок в handle_message 🐛"""
    message = AsyncMock(spec=Message)
    message.from_user = AsyncMock(id=999)
    message.answer = AsyncMock()
    
    # Мокаем get_user_state чтобы вернуть некорректные данные
    with patch('src.handlers.user.get_user_state', 
              new=AsyncMock(side_effect=Exception("Test error"))):
        
        await handle_message(message)
        
        # Проверяем, что ёжик отправил сообщение об ошибке
        message.answer.assert_called_with(
            "🆘 Произошла непредвиденная ошибка. Попробуйте позже или обратитесь в поддержку."
        )


# Удаляем ненужное:
# from src.utils.requests import get_user_info  # Этот беглец нам не нужен

# Оставляем только используемые импорты
from src.handlers.user import (
    start_handler, 
    process_registration,
    process_activation,
    handle_photo,
    handle_message  # ← Добавляем забытого ёжика 🦔
)