import pytest
from src.utils.db import safe_db_operation

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