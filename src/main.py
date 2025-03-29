import asyncio
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from src.utils.db import init_db
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logs directory
os.makedirs('logs', exist_ok=True)

logger = logging.getLogger(__name__)
load_dotenv('.env')

token = os.getenv('BOT_TOKEN')
if not token:
    logger.error("BOT_TOKEN not found in environment variables")
    sys.exit(1)
dp = Dispatcher()

async def main():
    try:
        logger.info("Starting bot initialization...")
        await init_db()
        logger.info("Database initialized successfully")
        
        from src.handlers import user, admin
        dp.include_router(user.router)
        dp.include_router(admin.router)
        
        logger.info("Bot started successfully")
        bot = Bot(token=token)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    asyncio.run(main())