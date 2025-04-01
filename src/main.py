import asyncio
import logging
import signal
from src.handlers import admin
from aiogram import Bot, Dispatcher
from src.config import BOT_TOKEN
from src.utils.db import init_db, test_admin_group
import os
import sys
import json
from src.utils.scheduler import check_and_send_lessons, check_scheduled_files

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
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
    courses_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'courses')
    if not os.path.exists(courses_dir):
        logger.warning(f"Courses directory not found: {courses_dir}")
        return
        
    logger.info("Validating media cache...")
    
    try:
        for course_dir in os.listdir(courses_dir):
            course_path = os.path.join(courses_dir, course_dir)
            cache_file = os.path.join(course_path, 'lessons.json')
            
            if not os.path.exists(cache_file):
                continue
                
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    lessons = json.load(f)
                    
                for lesson in lessons:
                    for content in lesson.get('content', []):
                        if content.get('type') in ['video', 'photo', 'audio', 'document']:
                            try:
                                await bot.get_file(content['file_id'])
                                logger.debug(f"✅ Valid media in lesson {lesson['lesson']}: {content.get('caption', 'untitled')}")
                            except Exception as e:
                                logger.warning(f"❌ Invalid media in lesson {lesson['lesson']}: {e}")
                                
            except Exception as e:
                logger.error(f"Error validating {course_dir}: {e}")
    except Exception as e:
        logger.error(f"Failed to validate media cache: {e}", exc_info=True)

# In shutdown handler
async def shutdown():
    logger.info("Shutting down...")
    from src.utils.db import close_db_connection
    await close_db_connection()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info(f"Cancelled {len(tasks)} tasks")
    loop.stop()
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    logger.info("Shutdown complete! 👋")

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
            async with asyncio.timeout(10):
                if not await test_admin_group(bot):
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
        asyncio.create_task(check_scheduled_files(bot))
        logger.info("All schedulers are running! 🚀")
        
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        raise
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Shutting down...")
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)