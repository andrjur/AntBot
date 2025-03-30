import asyncio
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from src.utils.db import init_db  # Restore 'src.'
import os
import sys
import signal

# Configure logging
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
load_dotenv('.env')

token = os.getenv('BOT_TOKEN')
if not token:
    logger.error("BOT_TOKEN not found in environment variables")
    sys.exit(1)
dp = Dispatcher()

LOCK_FILE = "bot.lock"

def check_single_instance():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still running
            os.kill(pid, 0)
            print(f"Bot is already running with PID {pid}")
            sys.exit(1)
        except (OSError, ValueError):
            # Process not running or invalid PID
            pass
    
    # Create lock file
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

async def main():
    try:
        check_single_instance()
        logger.info("Starting bot initialization...")
        await init_db()
        logger.info("Database initialized successfully")
        
        from src.handlers import user, admin  # Restore 'src.'
        dp.include_router(user.router)
        dp.include_router(admin.router)
        
        logger.info("Bot started successfully")
        bot = Bot(token=token)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        raise
    finally:
        # Remove lock file on exit
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == '__main__':
    asyncio.run(main())