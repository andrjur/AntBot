import os, sys, json, asyncio, logging

from aiogram import Bot, Dispatcher
from src.utils.db import test_admin_group, AsyncSessionFactory as async_session
from src.config import BOT_TOKEN
from src.utils.scheduler import check_and_send_lessons
from src.handlers import user, admin
from logging.handlers import RotatingFileHandler

from src.utils.models import Base
from src.utils.session import engine

# Configure logging at the root level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        RotatingFileHandler(
            'c:/Trae/AntBot/data/bot.log',
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=3,
            encoding='utf-8'
        ),
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
            os.kill(pid, 0)
            logger.error(f"Bot is already running with PID {pid}")
            sys.exit(1)
        except (OSError, ValueError):
            pass
    
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

async def validate_media_cache(bot: Bot):
    async with async_session() as session:
        # Use session for any DB operations
        pass


async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")  # Add logging

async def main():
    try:
        check_single_instance()
        logger.info("Starting bot initialization...")
        
        await init_models()  # Добавляем await перед init_models()

        logger.info("Database initialized successfully")
        
        dp.include_router(user.router)
        dp.include_router(admin.router)
        
        bot = Bot(token=BOT_TOKEN)
        
        # Test admin group communication with timeout
        logger.info("Testing admin group communication...")
        try:
            async with asyncio.timeout(10):
                async with async_session() as session:  # Создаём сессию здесь
                    if not await test_admin_group(bot, session):  # Теперь передаём оба параметра
                        logger.error("Failed to verify admin group communication")
                        sys.exit(1)
        except asyncio.TimeoutError:
            logger.error("Admin group test timed out")
            sys.exit(1)
            
        # Validate media cache
        await validate_media_cache(bot)
        
        logger.info("Bot started successfully")

        # Start schedulers
        asyncio.create_task(check_and_send_lessons(bot))
        logger.info("All schedulers are running! 🚀")
        
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        raise
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        from src.utils.cache import shutdown
        await shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Shutting down...")
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)