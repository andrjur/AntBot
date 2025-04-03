import os
import re
from dotenv import load_dotenv

load_dotenv()


DELAY_PATTERN = re.compile(r"_(\d+)(min|hour)\.")  # Supporting minutes and hours


# Test mode settings
TEST_LESSON_DELAY = 5*60  # 5 минут в секундах
TEST_FILE_DELAY = 30  # 30 секунд между файлами
NORMAL_LESSON_DELAY = 24*60*60  # 24 часа в секундах (было в минутах)

def is_test_mode():
    return bool(TEST_LESSON_DELAY)

TEST_MODE = is_test_mode()

def get_lesson_delay():
    """Get delay for next lesson based on test mode"""
    return TEST_LESSON_DELAY if TEST_MODE else NORMAL_LESSON_DELAY

def extract_delay_from_filename(filename: str) -> int:
    """Extract delay in seconds from filename pattern like 'name_XXmin.txt' or 'name_YYhour.txt'"""
    match = DELAY_PATTERN.search(filename)
    if match:
        amount = int(match.group(1))  # Извлекаем число (группа 1)
        unit = match.group(2)         # Извлекаем единицу измерения (группа 2: 'min' или 'hour')

        if unit == "min":
            delay_seconds = amount * 60
        elif unit == "hour":
            delay_seconds = amount * 3600
        else:
            delay_seconds = 0  # Неизвестная единица

        return TEST_FILE_DELAY if TEST_MODE else delay_seconds
    return 0  # Если совпадение не найдено, задержка равна 0


def no_get_file_delay(minutes: int) -> int:
    """Convert file delay based on test mode"""
    return TEST_FILE_DELAY if TEST_MODE else minutes * 60  # конвертируем минуты в секунды


# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Admin configuration
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID'))  # Convert to int for Telegram API
ADMIN_IDS = [int(id_) for id_ in os.getenv('ADMIN_IDS', '').split(',') if id_]  # List of admin IDs

# Database configuration
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'bot.db')



# Validate critical settings
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")
if not ADMIN_GROUP_ID:
    raise ValueError("ADMIN_GROUP_ID not found in .env")


# Проверить что DB_PATH существует
if not os.path.exists(os.path.dirname(DB_PATH)):
    os.makedirs(os.path.dirname(DB_PATH))