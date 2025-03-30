import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Admin configuration
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID'))  # Convert to int for Telegram API
ADMIN_IDS = [int(id_) for id_ in os.getenv('ADMIN_IDS', '').split(',') if id_]  # List of admin IDs

# Debug settings
TEST_LESSON_DELAY = '+5 minutes'  # Set to None for production mode
PRODUCTION_LESSON_DELAY = '+24 hours'

def get_lesson_delay():
    return TEST_LESSON_DELAY if TEST_LESSON_DELAY else PRODUCTION_LESSON_DELAY

def is_test_mode():
    return bool(TEST_LESSON_DELAY)

# Validate critical settings
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")
if not ADMIN_GROUP_ID:
    raise ValueError("ADMIN_GROUP_ID not found in .env")