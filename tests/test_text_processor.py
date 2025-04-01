import pytest
from src.utils.text_processor import process_markdown_simple, process_markdown, format_datetime
from datetime import datetime

def test_process_markdown_simple():
    """Тестируем простую обработку markdown 📝"""
    # HTML теги
    assert process_markdown_simple("<p>Привет</p>") == "Привет"
    assert process_markdown_simple("<b>Жирный</b>") == "*Жирный*"
    assert process_markdown_simple("<i>Курсив</i>") == "_Курсив_"
    
    # Множественные переносы
    assert process_markdown_simple("Строка1\n\n\n\nСтрока2") == "Строка1\n\nСтрока2"
    
    # Списки
    assert process_markdown_simple("—Пункт") == "-Пункт"

def test_process_markdown():
    """Тестируем продвинутый markdown 🎨"""
    # Базовая разметка
    assert process_markdown("*Жирный*") == "*Жирный*"
    assert process_markdown("_Курсив_") == "_Курсив_"
    
    # Спецсимволы
    assert process_markdown("Привет!") == "Привет\\!"
    assert process_markdown("[Ссылка]") == "\\[Ссылка\\]"
    
    # Списки
    assert process_markdown("- Пункт") == "\\- Пункт"
    assert process_markdown("1. Пункт") == "1\\. Пункт"
    
    # Вложенная разметка
    assert process_markdown("*Жирный _курсив_*") == "*Жирный _курсив_*"

def test_format_datetime():
    """Тестируем форматирование даты 📅"""
    dt = datetime(2024, 3, 14, 15, 9, 26)
    assert format_datetime(dt) == "14.03.2024 15:09"