import pytest
from unittest.mock import AsyncMock, patch, ANY
from aiogram.types import CallbackQuery
from src.handlers.admin import approve_homework, reject_homework
from src.keyboards.user import get_main_keyboard

@pytest.mark.asyncio
async def test_approve_homework(callback_mock, bot):
    """Тестируем одобрение домашки админом 📝"""
    callback_mock.data = "hw_approve_12345_python101_1"
    callback_mock.bot = bot
    
    # Мокаем все зависимости
    with patch('os.path.exists', return_value=True), \
         patch('os.path.dirname', return_value='/test/path'), \
         patch('glob.glob', return_value=['test_file.txt']), \
         patch('src.handlers.admin.safe_db_operation') as mock_db, \
         patch('src.handlers.admin.get_next_lesson', return_value=2), \
         patch('src.handlers.admin.get_main_keyboard', return_value=get_main_keyboard()):
        
        # Настраиваем мок БД
        db_mock = AsyncMock()
        db_mock.fetchone.return_value = ('2024-03-15 15:00:00',)
        mock_db.return_value = db_mock
        
        await approve_homework(callback_mock, bot)
        
        # Проверяем отправку сообщения студенту
        bot.send_message.assert_called_with(
            12345,
            "✅ Домашняя работа принята! Следующий урок будет доступен позже.",
            reply_markup=ANY
        )
        
        # Проверяем обновление БД
        assert mock_db.call_count > 0

@pytest.mark.asyncio
async def test_reject_homework(callback_mock, bot):
    """Тестируем отклонение домашки 🚫"""
    callback_mock.data = "hw_reject_12345_python101_1"
    callback_mock.bot = bot
    
    with patch('src.handlers.admin.safe_db_operation') as mock_db, \
         patch('src.handlers.admin.process_homework_status', return_value=True):
        
        mock_db.return_value.fetchone.return_value = (1,)  # current_lesson
        await reject_homework(callback_mock, bot)
        
        # Проверяем сообщение студенту
        bot.send_message.assert_called_with(
            12345,
            "❌ Ваша домашняя работа отклонена.\nПожалуйста, отправьте новое фото."
        )