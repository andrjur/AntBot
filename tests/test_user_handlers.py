import pytest
from unittest.mock import AsyncMock, patch
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.handlers.user import (
    start_handler, 
    process_registration
)
from src.utils.db import add_user
from src.keyboards.user import get_main_keyboard

@pytest.mark.asyncio
async def test_start_handler_new_user(message_mock, bot, state_mock):
    """Тестируем /start для нового пользователя 👋"""
    message_mock.bot = bot
    
    with patch('src.handlers.user.get_user', return_value=None):
        await start_handler(message_mock, state_mock)
        state_mock.set_state.assert_called_once_with("registration")  # Исправили на строку вместо FSMFillForm
        message_mock.answer.assert_called_with(
            "Добро пожаловать! Пожалуйста, введите ваше имя:"
        )

@pytest.mark.asyncio
async def test_registration_success(message_mock, state_mock):
    message_mock.text = "Тест Тестович"  # Явно устанавливаем текст
    message_mock.from_user.id = 123
    
    # Меняем на асинхронный assert как правильный ключ к замку 🔑
    with patch('src.handlers.user.add_user', new=AsyncMock()) as mock_add:
        await process_registration(message_mock, state_mock)
        mock_add.assert_awaited_once_with(123, "Тест Тестович")  # Используем assert_awaited
        state_mock.clear.assert_called_once()  # Проверяем очистку состояния
        message_mock.answer.assert_called_with(
            "Регистрация завершена! Введите кодовое слово для активации курса:"
        )