from src.utils.models import User, UserCourse  # Исправляем импорт
from src.utils.db import safe_db_operation
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
# Change from:
# from src.utils.db import get_user_info, verify_course_enrollment
# To:
from src.utils.requests import get_user_info
from src.utils.courses import verify_course_enrollment
from src.utils.models import User, UserCourse, Course

# Теперь тесты будут использовать фикстуру setup_db с алхимией
@pytest.mark.asyncio
async def test_select_operation(setup_db):
    """Тест SELECT-запроса 🔍"""
    result = await safe_db_operation(
        "SELECT name FROM sqlite_master WHERE type='table'",
        fetch_one=True
    )
    assert result is not None, "Должна быть хотя бы одна таблица"

@pytest.mark.asyncio
async def test_insert_and_select(setup_db):
    """Тест INSERT и SELECT операций ✍️"""
    name = "Тестовый Тестович"
    await safe_db_operation(
        "INSERT INTO users (user_id, name) VALUES (?, ?)",
        (42, name)
    )
    
    result = await safe_db_operation(
        "SELECT name FROM users WHERE user_id = ?",
        (42,),
        fetch_one=True
    )
    assert result is not None, "Результат не должен быть пустым"
    assert result[0] == name, "Имя должно совпадать"


@pytest.mark.asyncio
async def test_get_user_info(setup_db, async_session: AsyncSession):
    # Подготовка тестовых данных
    user = User(user_id=1, name="Test User")
    course = Course(id="test", name="Test Course", code="test")
    user_course = UserCourse(
        user_id=1,
        course_id="test",
        current_lesson=1,
        version_id="basic",
        first_lesson_time=datetime.now()
    )
    
    async_session.add_all([user, course, user_course])
    await async_session.commit()
    
    # Тестирование
    result = await get_user_info(async_session, 1)
    assert "Test User" in result
    assert "Test Course" in result
    assert "basic" in result

@pytest.mark.asyncio
async def test_verify_course_enrollment(setup_db, async_session: AsyncSession):
    # Подготовка данных
    user = User(user_id=2, name="Enrolled User")
    course = Course(id="course2", name="Course 2", code="c2")
    user_course = UserCourse(
        user_id=2,
        course_id="course2",
        version_id="premium"
    )
    
    async_session.add_all([user, course, user_course])
    await async_session.commit()
    
    # Тестирование
    version, name, _ = await verify_course_enrollment(async_session, 2, "course2")
    assert version == "premium"
    assert name == "Enrolled User"
    
    # Проверка ошибки для неподписанного пользователя
    with pytest.raises(ValueError):
        await verify_course_enrollment(async_session, 99, "course2")

# Remove this import:
# from src.utils.db import init_db