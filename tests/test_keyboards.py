import pytest
from src.keyboards.markup import create_main_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def test_create_main_menu_without_course():
    """Test creating main menu without course_id"""
    keyboard = create_main_menu()
    
    # Check that keyboard is an InlineKeyboardMarkup
    assert isinstance(keyboard, InlineKeyboardMarkup)
    
    # Check that we have 2 rows (resend lesson and help)
    assert len(keyboard.inline_keyboard) == 2
    
    # Check first row has resend_lesson button
    assert len(keyboard.inline_keyboard[0]) == 1
    assert keyboard.inline_keyboard[0][0].text == "📚 Прислать урок заново"
    assert keyboard.inline_keyboard[0][0].callback_data == "resend_lesson"
    
    # Check second row has help button
    assert len(keyboard.inline_keyboard[1]) == 1
    assert keyboard.inline_keyboard[1][0].text == "❓ Помощь"
    assert keyboard.inline_keyboard[1][0].callback_data == "help"


def test_create_main_menu_with_course():
    """Test creating main menu with course_id"""
    course_id = "test_course"
    keyboard = create_main_menu(course_id)
    
    # Check that keyboard is an InlineKeyboardMarkup
    assert isinstance(keyboard, InlineKeyboardMarkup)
    
    # Check that we have 3 rows (resend lesson, view homeworks, and help)
    assert len(keyboard.inline_keyboard) == 3
    
    # Check first row has resend_lesson button
    assert len(keyboard.inline_keyboard[0]) == 1
    assert keyboard.inline_keyboard[0][0].text == "📚 Прислать урок заново"
    assert keyboard.inline_keyboard[0][0].callback_data == "resend_lesson"
    
    # Check second row has view homeworks button
    assert len(keyboard.inline_keyboard[1]) == 1
    assert keyboard.inline_keyboard[1][0].text == "👥 Смотреть работы других"
    assert keyboard.inline_keyboard[1][0].callback_data == f"view_homeworks_{course_id}_current"
    
    # Check third row has help button
    assert len(keyboard.inline_keyboard[2]) == 1
    assert keyboard.inline_keyboard[2][0].text == "❓ Помощь"
    assert keyboard.inline_keyboard[2][0].callback_data == "help"


def test_button_properties():
    """Test that buttons have correct properties"""
    keyboard = create_main_menu("test_course")
    
    # Check all buttons in the keyboard
    for row in keyboard.inline_keyboard:
        for button in row:
            # Check that button is an InlineKeyboardButton
            assert isinstance(button, InlineKeyboardButton)
            
            # Check that button has text and callback_data
            assert button.text is not None
            assert button.callback_data is not None
            
            # Check that callback_data is a string
            assert isinstance(button.callback_data, str)


def test_callback_data_format():
    """Test that callback data has correct format"""
    course_id = "test_course"
    keyboard = create_main_menu(course_id)
    
    # Check view homeworks button callback data format
    view_homeworks_button = keyboard.inline_keyboard[1][0]
    assert view_homeworks_button.callback_data.startswith("view_homeworks_")
    assert course_id in view_homeworks_button.callback_data
    assert view_homeworks_button.callback_data.endswith("_current")