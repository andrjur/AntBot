import pytest
from unittest.mock import AsyncMock, patch
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

# Change imports to absolute path
from src.handlers.user import start_handler, process_registration
from src.utils.db import add_user
from src.keyboards.markup import create_main_menu

@pytest.fixture
def message_mock():
    msg = AsyncMock(spec=Message)
    msg.from_user.id = 123
    msg.text = "Иван +79991234567"  # Fixed format for name and phone
    return msg

@pytest.mark.asyncio
async def test_start_handler_new_user():
    message = AsyncMock(spec=Message)
    message.from_user.id = 123
    state = AsyncMock(spec=FSMContext)
    
    with patch('src.handlers.user.get_user', new=AsyncMock(return_value=None)):
        await start_handler(message, state)
        message.answer.assert_called_with("Добро пожаловать! Введите ваше имя и номер телефона:")
        state.set_state.assert_called_with("registration")

@pytest.mark.asyncio
async def test_start_handler_existing_user():
    message = AsyncMock(spec=Message)
    message.from_user.id = 123
    state = AsyncMock(spec=FSMContext)
    
    with patch('src.handlers.user.get_user', new=AsyncMock(return_value={"user_id": 123})), \
         patch('src.handlers.user.create_main_menu', return_value=("Menu text", None)):
        await start_handler(message, state)
        message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_registration_success(message_mock):
    state = AsyncMock(spec=FSMContext)
    
    with patch('src.handlers.user.add_user', new=AsyncMock()) as mock_add:
        await process_registration(message_mock, state)
        
        name, phone = message_mock.text.split(" ", 1)
        mock_add.assert_awaited_with(
            user_id=123,
            name=name,
            phone=phone
        )
        state.clear.assert_called_once()
        message_mock.answer.assert_called_with(
            "Регистрация завершена! Введите кодовое слово для активации курса:"
        )

@pytest.mark.asyncio
async def test_registration_invalid_phone():
    message = AsyncMock(spec=Message)
    message.text = "invalid_phone"
    state = AsyncMock(spec=FSMContext)
    
    await process_registration(message, state)
    message.answer.assert_called_with(
        "Неверный формат номера. Введите в формате +79991234567"
    )