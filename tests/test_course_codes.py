import pytest
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db import verify_course_code, init_db

@pytest.fixture
async def setup_db():
    """Инициализация тестовой базы данных"""
    await init_db(test_mode=True)
    yield
    # Здесь можно добавить очистку тестовой БД

@pytest.mark.asyncio
async def test_valid_course_codes(setup_db):
    """Тест на проверку валидных кодовых слов"""
    # Проверяем код "роза" для курса "Женственность"
    success, result = await verify_course_code("роза", 12345)
    assert success is True, f"Код 'роза' должен быть валидным, но получено: {result}"
    assert result == "femininity", f"Код 'роза' должен активировать курс 'femininity', но получено: {result}"
    
    # Проверяем код "фиалка" для курса "Женственность (С проверкой ДЗ)"
    success, result = await verify_course_code("фиалка", 54321)
    assert success is True, f"Код 'фиалка' должен быть валидным, но получено: {result}"
    assert result == "femininity_admin_check", f"Код 'фиалка' должен активировать курс 'femininity_admin_check', но получено: {result}"
    
    # Проверяем код "лепесток" для курса "Женственность (Премиум)"
    success, result = await verify_course_code("лепесток", 67890)
    assert success is True, f"Код 'лепесток' должен быть валидным, но получено: {result}"
    assert result == "femininity_premium", f"Код 'лепесток' должен активировать курс 'femininity_premium', но получено: {result}"

@pytest.mark.asyncio
async def test_invalid_course_codes(setup_db):
    """Тест на проверку невалидных кодовых слов"""
    # Проверяем невалидный код
    success, result = await verify_course_code("неправильный_код", 12345)
    assert success is False, "Невалидный код должен возвращать False"
    
    # Проверяем пустой код
    success, result = await verify_course_code("", 12345)
    assert success is False, "Пустой код должен возвращать False"
    
    # Проверяем код с пробелами
    success, result = await verify_course_code("  роза  ", 12345)
    assert success is True, "Код с пробелами должен быть обработан корректно"

@pytest.mark.asyncio
async def test_already_enrolled(setup_db):
    """Тест на проверку повторной активации курса"""
    # Сначала активируем курс
    success, _ = await verify_course_code("роза", 99999)
    assert success is True, "Первая активация должна быть успешной"
    
    # Пытаемся активировать тот же курс повторно
    success, result = await verify_course_code("роза", 99999)
    assert success is False, "Повторная активация должна возвращать False"
    assert "уже активирован" in result.lower(), f"Сообщение должно содержать информацию о том, что курс уже активирован, но получено: {result}"

if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__]))