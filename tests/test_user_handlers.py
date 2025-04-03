import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.handlers.user import start_handler,  process_registration,  process_activation
from src.keyboards.user import get_main_keyboard
from src.utils.requests import add_user, verify_course_code

@pytest.fixture
def db_session():
    """Fixture for database session"""
    return MagicMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_registration_success(message_mock, state_mock, db_session):
    message_mock.text = "Тест Тестович"
    message_mock.from_user.id = 123
    
    with patch('src.handlers.user.AsyncSessionFactory', return_value=db_session), \
         patch('src.utils.requests.add_user', new=AsyncMock(return_value=True)) as mock_add:
        await process_registration(message_mock, state_mock)
        mock_add.assert_awaited_once_with(db_session, 123, "Тест Тестович")
        state_mock.clear.assert_called_once()
        message_mock.answer.assert_called_with(
            "Регистрация завершена! Введите кодовое слово для активации курса:"
        )

@pytest.mark.asyncio
async def test_activation_success(message_mock, state_mock, db_session):
    message_mock.text = "роза"
    message_mock.from_user.id = 123
    
    with patch('src.handlers.user.AsyncSessionFactory', return_value=db_session), \
         patch('src.utils.requests.verify_course_code', return_value=(True, "course123")):
        await process_activation(message_mock, state_mock)
        message_mock.answer.assert_called_with(
            "✅ Курс активирован!\n\n👋 Привет, ...",
            reply_markup=ANY
        )

@pytest.mark.asyncio
async def test_activation_failure(message_mock, state_mock, db_session):
    message_mock.text = "неверный_код"
    message_mock.from_user.id = 123
    
    with patch('src.handlers.user.AsyncSessionFactory', return_value=db_session), \
         patch('src.utils.requests.verify_course_code', return_value=(False, "Неверный код")):
        await process_activation(message_mock, state_mock)
        message_mock.answer.assert_called_with("Неверный код")