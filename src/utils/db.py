import logging, asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from functools import wraps  # Add this import at the top
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.config import ADMIN_GROUP_ID
import logging
from sqlalchemy import text  # Add this import at the top
# Добавляем в начало файла, где другие импорты
from src.utils.models import User, UserCourse, Homework, ScheduledFile


logger = logging.getLogger(__name__)

async def test_admin_group(bot: Bot, session: AsyncSession) -> bool:
    """Test communication with admin group 🎯 (now with SQLAlchemy)"""
    try:
        if not ADMIN_GROUP_ID:
            logger.error("Admin group ID not configured")
            return False
            
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data="admin_test"
            )
        ]])
        
        await bot.send_message(
            ADMIN_GROUP_ID,
            "🔄 Проверка связи с админской группой...",
            reply_markup=markup
        )
        
        # Example of using the session for logging
        await session.execute(text("SELECT 1"))  # Wrap SQL in text()
        return True
        
    except Exception as e:
        logger.error(f"Failed to test admin group: {e}")
        return False

# Константы
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 5

async def verify_course_enrollment(
    session: AsyncSession, 
    user_id: int, 
    course_id: str
) -> Tuple[str, str, datetime]:
    """Проверка подписки пользователя на курс"""
    result = await session.execute(
        select(
            UserCourse.version_id,
            User.name,
            UserCourse.first_lesson_time
        )
        .join(User, User.user_id == UserCourse.user_id)
        .where(UserCourse.user_id == user_id)
        .where(UserCourse.course_id == course_id)
    )
    
    enrollment = result.first()
    if not enrollment:
        raise ValueError(f"Пользователь {user_id} не подписан на курс {course_id}")
        
    return tuple(enrollment) if enrollment else None

async def notify_admins_with_retry(
    bot: Bot,
    file_id: str,
    user_data: dict,
    markup: InlineKeyboardMarkup,
    retry_count: int = DEFAULT_RETRY_COUNT
) -> bool:
    """Отправка уведомления админам с повторами"""
    for attempt in range(retry_count):
        try:
            await bot.send_photo(
                chat_id=ADMIN_GROUP_ID,
                photo=file_id,
                caption=(
                    f"📝 Новое домашнее задание!\n"
                    f"👤 Ученик: {user_data['name']}\n"
                    f"📚 Курс: {user_data['course_id']}\n"
                    f"📊 Тариф: {user_data['version_id']}\n"
                    f"📝 Урок: {user_data['lesson']}"
                ),
                reply_markup=markup
            )
            return True
            
        except Exception as e:
            logger.warning(f"Попытка {attempt+1} не удалась: {e}")
            if attempt < retry_count - 1:
                await asyncio.sleep(DEFAULT_RETRY_DELAY)
                
    return False

async def get_pending_homeworks(session: AsyncSession) -> list:  # Упрощаем аннотацию
    """Get list of pending homeworks using ORM"""
    try:
        result = await session.execute(
            select(Homework)
            .join(User, Homework.user_id == User.user_id)
            .where(Homework.status == 'pending')
            .order_by(Homework.submission_time)
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Error getting pending homeworks: {e}")
        return []

async def get_next_lesson(session: AsyncSession, user_id: int, course_id: str) -> int:
    """Get next lesson number using ORM"""
    try:
        user_course = await session.get(UserCourse, (user_id, course_id))
        return user_course.current_lesson + 1 if user_course else 1
    except SQLAlchemyError as e:
        logger.error(f"Error getting next lesson: {e}")
        return 1

async def cleanup_old_scheduled_files(session: AsyncSession, days: int = 7) -> int:
    """Cleanup old scheduled files using ORM"""
    try:
        result = await session.execute(
            delete(ScheduledFile)
            .where(ScheduledFile.sent == True)
            .where(ScheduledFile.send_at < datetime.now() - timedelta(days=days))
        )
        await session.commit()
        return result.rowcount
    except SQLAlchemyError as e:
        logger.error(f"Error cleaning scheduled files: {e}")
        await session.rollback()
        return 0


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging
from functools import wraps

# Настройка алхимического двигателя 🚀
DATABASE_URL = "sqlite+aiosqlite:///./antbot.db"
engine = create_async_engine(DATABASE_URL)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

def safe_db_operation(func):
    """Декоратор для безопасной работы с БД (без fetch_one)"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            async with AsyncSessionFactory() as session:
                kwargs['session'] = session
                result = await func(*args, **kwargs)
                await session.commit()
                return result
        except SQLAlchemyError as e:
            logging.error(f"Database error in {func.__name__}: {e}")
            if 'session' in locals():
                await session.rollback()
            return None
    return wrapper

# async def get_user(user_id: int) -> Optional[User]:
#     """Получаем пользователя по ID (теперь с правильными параметрами)"""
#     try:
#         async with AsyncSessionFactory() as session:
#             result = await session.get(User, user_id)
#             return result
#     except SQLAlchemyError as e:
#         logger.error(f"Error getting user {user_id}: {e}")
#         return None

async def get_pending_homeworks(session: AsyncSession) -> List[Homework]:
    """Get list of pending homeworks (теперь с правильным типом)"""
    try:
        result = await session.execute(
            select(Homework)
            .join(User, Homework.user_id == User.user_id)
            .where(Homework.status == 'pending')
            .order_by(Homework.submission_time)
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Error getting pending homeworks: {e}")
        return []

async def get_db_session() -> AsyncSession:
    """Генератор сессий для зависимостей FastAPI"""
    async with AsyncSessionFactory() as session:
        try:
            yield session

        except SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()

# Example usage:
@safe_db_operation
async def get_user_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.user_id)))
    return result.scalar()



# Add at the bottom of the file
async_session = AsyncSessionFactory  # Просто алиас


# async def предсказать_следующий_урок(сеанс: AsyncSession, id_ученика: int, id_курса: str) -> int:
#     """Гадание на кофейной гуще SQLAlchemy"""
#     try:
#         свиток_ученика = await сеанс.get(UserCourse, (id_ученика, id_курса))
#         return свиток_ученика.current_lesson + 1 if свиток_ученика else 1
#     except SQLAlchemyError as провал_гадания:
#         logger.error(f"Хрустальный шар помутнел: {провал_гадания}")
#         return 1  # Всегда можно начать с первого урока, как в алхимии - с основ



    