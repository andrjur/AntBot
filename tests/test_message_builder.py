import pytest
from src.utils.message_builder import build_welcome_message, build_help_message

def test_build_welcome_message():
    """Тестируем сборку приветственного сообщения 👋"""
    name = "Тестовый Тестович"
    message = build_welcome_message(name)
    
    # Проверяем наличие ключевых элементов
    assert name in message
    assert "Привет" in message
    assert "!" in message

def test_build_help_message():
    """Тестируем сборку сообщения помощи 🆘"""
    message = build_help_message()
    
    # Проверяем наличие команд в справке
    assert "/start" in message
    assert "/help" in message
    assert "/activate" in message