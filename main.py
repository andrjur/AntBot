import asyncio
import logging
try:
    from aiogram import Bot, Dispatcher
except ImportError:
    print("Error: aiogram package is not installed. Please install it using 'pip install aiogram'")
    exit(1)
from dotenv import load_dotenv
import os
from aiogram import F
from aiogram.types import Message, CallbackQuery
from utils.db import set_user_state, get_user_state, submit_homework

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('config.env')

# Initialize bot and dispatcher
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

async def main():
    # Import handlers
    from handlers import user, admin
    
    # Register routers
    dp.include_router(user.router)
    dp.include_router(admin.router)
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


from aiogram import F
from aiogram.types import Message, CallbackQuery
from utils.db import set_user_state, get_user_state, submit_homework

async def handle_homework(message: Message):
    user_state = await get_user_state(message.from_user.id)
    
    if user_state and user_state[0] == "waiting_homework":
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        await submit_homework(
            message.from_user.id,
            user_state[1],  # course_id
            user_state[2],  # lesson
            file_id
        )
        await message.answer("📝 Домашняя работа принята! Ожидайте проверки.")
        await set_user_state(message.from_user.id, None)

# Add this to your handlers
dp.message.register(handle_homework, F.content_type.in_({'photo', 'document'}))