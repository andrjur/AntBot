import pytest
from src.handlers.user import start_handler, process_registration, process_activation
from src.utils.db import get_user, get_user_info
from aiogram.types import Message, User
from aiogram.fsm.context import FSMContext

@pytest.mark.asyncio
async def test_registration_flow():
    # Mock message and state
    message = AsyncMock(Message)
    message.from_user = MagicMock(User)
    message.from_user.id = 12345
    message.text = "Test User"
    
    state = AsyncMock(FSMContext)
    
    # Test registration
    await process_registration(message, state)
    
    # Verify user was added
    user = await get_user(12345)
    assert user is not None
    assert user[1] == "Test User"
    
    # Verify state was cleared
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_course_activation():
    message = AsyncMock(Message)
    message.from_user.id = 12345
    message.text = "роза"  # Valid course code
    
    state = AsyncMock(FSMContext)
    
    # Test activation
    await process_activation(message, state)
    
    # Verify course was activated
    user_info = await get_user_info(12345)
    assert "Женственность" in user_info
    assert "Текущий урок: 1" in user_info

@pytest.mark.asyncio
async def test_homework_submission(bot):
    # Mock photo message
    photo_message = AsyncMock(Message)
    photo_message.photo = [MagicMock(file_id="test_photo")]
    photo_message.from_user.id = 12345
    
    # Submit homework
    await submit_homework(photo_message)
    
    # Verify forwarded to admin group
    bot.send_photo.assert_called_with(
        chat_id=ADMIN_GROUP_ID,
        photo="test_photo",
        caption="Homework from User: Test User"
    )