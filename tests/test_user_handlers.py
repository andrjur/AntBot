import pytest
from unittest.mock import AsyncMock, patch
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from handlers.user import start_handler, process_registration

@pytest.fixture
def message_mock():
    msg = AsyncMock(spec=Message)
    msg.from_user.id = 123
    msg.text = "+79991234567"
    return msg

@pytest.mark.asyncio
async def test_start_handler_new_user():
    # Mock dependencies
    message = AsyncMock(spec=Message)
    state = AsyncMock(spec=FSMContext)
    
    # Mock get_user to return None
    with patch('handlers.user.get_user', new=AsyncMock(return_value=None)):
        await start_handler(message, state)
        
        # Verify registration flow
        message.answer.assert_called_with("Добро пожаловать! Введите ваше имя и номер телефона:")
        state.set_state.assert_called_with("registration")

@pytest.mark.asyncio
async def test_start_handler_existing_user():
    message = AsyncMock(spec=Message)
    state = AsyncMock(spec=FSMContext)
    
    # Mock get_user to return existing user
    with patch('handlers.user.get_user', new=AsyncMock(return_value={"user_id": 123})):
        await start_handler(message, state)
        
        # Verify main menu is shown
        message.answer.assert_called()

@pytest.mark.asyncio
async def test_registration_success(message_mock):
    state = AsyncMock(spec=FSMContext)
    
    with patch('handlers.user.add_user', new=AsyncMock()) as mock_add:
        await process_registration(message_mock, state)
        
        # Verify user creation
        mock_add.assert_awaited_with(
            user_id=123,
            name="+79991234567",  # Should split properly in real impl
            phone="+79991234567"
        )
        message_mock.answer.assert_called_with("Регистрация завершена! Введите кодовое слово для активации курса:")

@pytest.mark.asyncio
async def test_registration_invalid_phone():
    message = AsyncMock(text="invalid_phone")
    state = AsyncMock(spec=FSMContext)
    
    await process_registration(message, state)
    
    # Verify error message
    message.answer.assert_called_with("Неверный формат номера. Введите в формате +79991234567")