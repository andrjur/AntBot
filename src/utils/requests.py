import json  # Добавляем этот импорт для работы с JSON
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, Course, UserCourse, Homework
import logging
from src.utils.courses import verify_code  # Добавляем этот импорт
from sqlalchemy.exc import SQLAlchemyError
from .session import AsyncSessionFactory
from typing import List, Optional  # Для аннотации типов


async def get_pending_homeworks(session: AsyncSession) -> List[Homework]:
    """Получаем список домашних работ на проверку (как в старые добрые времена)"""
    try:
        result = await session.execute(
            select(Homework)
            .join(User, Homework.user_id == User.user_id)
            .where(Homework.status == 'pending')
            .order_by(Homework.submission_time)
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при получении домашних работ: {e}")
        return []  # Возвращаем пустой список, как пустую корзину для проверки

async def add_user(session: AsyncSession, user_id: int, name: str, course_id: str = None) -> bool:
    """Добавляем пользователя с возможной привязкой к курсу"""
    try:
        user = User(user_id=user_id, name=name)
        session.add(user)
        
        if course_id:
            # Если есть курс - добавляем и его
            version_id = "self_check"  # Или получаем из курса
            await enroll_user_in_course(session, user_id, course_id, version_id)
            
        await session.commit()
        return True
    except Exception as e:
        logging.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
        await session.rollback()
        return False



async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получаем пользователя по ID (версия для спортсменов-олимпийцев)"""
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()  # Возвращаем None если пользователь не найден

async def enroll_user_in_course(session: AsyncSession, user_id: int, course_id: str, version_id: str) -> bool:
    try:
        user_course = UserCourse(
            user_id=user_id,
            course_id=course_id,
            version_id=version_id,
            current_lesson=1
        )
        session.add(user_course)
        await session.commit()
        return True
    except Exception as e:
        logging.error(f"Error enrolling user {user_id} in course {course_id}: {e}")
        await session.rollback()
        return False

async def submit_homework(session: AsyncSession, user_id: int, 
                         course_id: str, lesson: int, file_id: str) -> bool:
    try:
        # Проверяем, не отправил ли уже ДЗ
        existing = await session.execute(
            select(Homework).where(
                Homework.user_id == user_id,
                Homework.course_id == course_id,
                Homework.lesson == lesson
            )
        )
        if existing.scalar():
            return False  # Уже отправлял
            
        # Сохраняем ДЗ
        homework = Homework(
            user_id=user_id,
            course_id=course_id,
            lesson=lesson,
            status='pending',
            file_id=file_id,
            submission_time=func.now()
        )
        session.add(homework)
        await session.commit()
        
        # Уведомляем админов
        await notify_admins(course_id, user_id, lesson)
        return True
        
    except Exception as e:
        logging.error(f"Ошибка сохранения ДЗ: {e}")
        await session.rollback()
        return False


async def get_user_info(session: AsyncSession, user_id: int) -> str:
    """Получаем инфу о пользователе в красивом формате"""
    try:
        # Получаем данные пользователя и его курса одним запросом
        stmt = select(
            User.name,
            UserCourse.course_id,
            UserCourse.current_lesson,
            UserCourse.version_id,
            UserCourse.first_lesson_time
        ).join(
            UserCourse, User.user_id == UserCourse.user_id, isouter=True
        ).where(User.user_id == user_id)
        
        result = await session.execute(stmt)
        user_data = result.first()
        
        if not user_data:
            return "❌ Данные пользователя не найдены"
            
        name, course_id, lesson, version_id, first_lesson = user_data
        
        # Если у пользователя нет курса
        if not course_id:
            return f"👋 Привет, {name}!\n\nУ вас пока нет активных курсов."
            
        # Форматируем дату начала курса
        first_lesson_formatted = first_lesson.strftime("%d.%m.%Y") if first_lesson else "неизвестно"
        
        # Получаем название курса
        course = await session.execute(select(Course.name).where(Course.id == course_id))
        course_name = course.scalar() or "Неизвестный курс"
        
        # Формируем красивый ответ
        return (
            f"👋 Привет, {name}!\n\n"
            f"🎓 Курс: {course_name}\n"
            f"📚 Текущий урок: {lesson}\n"
            f"🗓 Начало курса: {first_lesson_formatted}\n"
            f"🔑 Тариф: {version_id}"
        )
        
    except Exception as e:
        logging.error(f"Ошибка при получении информации о пользователе: {e}")
        return "❌ Ошибка получения данных"


async def verify_course_code(code: str, user_id: int) -> tuple[bool, str]:
    """Проверяем любой валидный код из courses.json"""
    try:
        with open('c:/Trae/AntBot/data/courses.json', 'r', encoding='utf-8') as f:
            courses = json.load(f)
        
        # Ищем код во всех курсах
        for course_id, course_data in courses.items():
            for version in course_data.get('versions', []):
                if version.get('code', '').lower() == code.lower():
                    async with AsyncSessionFactory() as session:
                        # Проверяем, не активирован ли уже курс
                        stmt = select(UserCourse).where(
                            UserCourse.user_id == user_id,
                            UserCourse.course_id == course_id
                        )
                        if await session.scalar(stmt):
                            return False, "Этот курс уже активирован"
                        
                        # Записываем на курс
                        if await enroll_user_in_course(session, user_id, course_id, version['id']):
                            return True, f"Курс '{course_data['name']}' активирован"
                        return False, "Ошибка активации курса"
        
        return False, "Неверное кодовое слово"
    
    except Exception as e:
        logging.error(f"Ошибка при проверке кода: {e}")
        return False, "Ошибка системы. Попробуй позже"


async def set_user_state(session: AsyncSession, user_id: int, state: str) -> bool:
    """Update user's state in database"""
    try:
        stmt = update(User).where(User.user_id == user_id).values(state=state)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logging.error(f"Error updating state for user {user_id}: {e}")
        await session.rollback()
        return False


# Add these imports if not already present
from sqlalchemy import select
from .models import User, UserCourse

async def get_user_info(user_id: int):
    """Get user info from database"""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User)
            .where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()


async def get_user_state(user_id: int) -> tuple:
    """Get current user state from database"""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(UserState)
            .where(UserState.user_id == user_id)
        )
        state = result.scalar_one_or_none()
        if state:
            return (state.state, state.course_id, state.lesson)
        return None


# Добавляем где-нибудь в начале
get_user_db = get_user  # Просто алиас
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError

def safe_db_operation(func):
    """Декоратор для безопасной работы с БД"""
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

