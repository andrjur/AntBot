import asyncio
import logging
from src.handlers import admin
from aiogram import Bot, Dispatcher
from src.config import BOT_TOKEN  # Import from config instead
from src.utils.db import init_db, test_admin_group  # Add this import
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

if not BOT_TOKEN:
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
        
        from src.handlers import user, admin
        dp.include_router(user.router)
        dp.include_router(admin.router)
        
        bot = Bot(token=BOT_TOKEN)
        
        # Test admin group communication with timeout
        logger.info("Testing admin group communication...")
        try:
            async with asyncio.timeout(10):  # 10 seconds timeout
                if not await test_admin_group(bot):
                    logger.error("Failed to verify admin group communication")
                    sys.exit(1)
        except asyncio.TimeoutError:
            logger.error("Admin group test timed out")
            sys.exit(1)
            
        logger.info("Bot started successfully")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        raise
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == '__main__':
    asyncio.run(main())