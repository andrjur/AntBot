import pytest
from datetime import datetime, timedelta
from src.utils.scheduler import format_next_lesson_time, parse_next_lesson_time
from src.services.scheduler import schedule_lessons
from src.config import extract_delay_from_filename, TEST_MODE, TEST_FILE_DELAY
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_format_next_lesson_time():
    """Тестируем форматирование времени следующего урока ⏰"""
    # Тестируем разные интервалы
    assert format_next_lesson_time("1d") == "24 часа"
    assert format_next_lesson_time("2d") == "48 часов"
    assert format_next_lesson_time("7d") == "неделю"
    assert format_next_lesson_time("14d") == "2 недели"

@pytest.mark.asyncio
async def test_extract_delay_from_filename():
    """Тестируем извлечение задержки из имени файла ⏰"""
    # Отключаем тестовый режим для проверки реальных значений
    with patch('src.config.TEST_MODE', False):
        assert extract_delay_from_filename("task_15min.txt") == 15 * 60  # 15 минут в секундах
        assert extract_delay_from_filename("theory_1hour.txt") == 1 * 3600  # 1 час в секундах
        assert extract_delay_from_filename("intro.txt") == 0  # Без задержки
        assert extract_delay_from_filename("practice_2hour.txt") == 2 * 3600  # 2 часа в секундах

@pytest.mark.asyncio
async def test_parse_next_lesson_time():
    """Тестируем парсинг времени следующего урока 📅"""
    now = datetime.now()
    
    # Проверяем разные форматы
    assert parse_next_lesson_time("1d") == now + timedelta(days=1)
    assert parse_next_lesson_time("2d") == now + timedelta(days=2)
    assert parse_next_lesson_time("1w") == now + timedelta(weeks=1)

@pytest.mark.asyncio
async def test_schedule_lessons():
    """Тестируем отправку уроков по расписанию ⏰"""
    # Создаем мок для send_lesson
    mock_send_lesson = AsyncMock()
    
    # Патчим aiosqlite и добавляем send_lesson в модуль scheduler
    with patch('src.services.scheduler.aiosqlite.connect') as mock_connect, \
         patch('src.services.scheduler.send_lesson', mock_send_lesson):
        
        # Настраиваем мок для базы данных
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        mock_db.execute.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(123, 'python101', 1)]
        
        # Вызываем тестируемую функцию
        await schedule_lessons()
        
        # Проверяем, что send_lesson был вызван с правильными параметрами
        mock_send_lesson.assert_called_once_with(123, 'python101', 1)