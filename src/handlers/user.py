from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
import logging
from aiogram.fsm.context import FSMContext
from src.utils.requests import (  # Измененный импорт
    add_user, get_user, get_user_info, verify_course_code,
    submit_homework, set_user_state  # Теперь функция на месте!
)
from src.keyboards.user import get_main_keyboard  # Добавили импорт клавиатуры
from src.utils.lessons import get_lesson_materials
from src.utils.db import safe_db_operation  # Устаревший импорт
from src.utils.requests import get_user  # 2-04
from src.utils.text_processor import process_markdown_simple
from src.utils.db import AsyncSessionFactory
from src.utils.requests import (
    get_user, add_user, verify_course_code, get_user_info
)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
import logging
from aiogram.fsm.context import FSMContext
from src.utils.requests import (  # Измененный импорт
    add_user, get_user, get_user_info, verify_course_code,
    submit_homework, set_user_state  # Теперь функция на месте!
)
from src.keyboards.user import get_main_keyboard  # Добавили импорт клавиатуры
from src.utils.lessons import get_lesson_materials
from src.utils.db import safe_db_operation  # Устаревший импорт
from src.utils.requests import get_user  # 2-04
from src.utils.text_processor import process_markdown_simple
from src.utils.db import AsyncSessionFactory
from src.utils.requests import (
    get_user, add_user, verify_course_code, get_user_info
)
from src.utils.requests import (
    add_user, get_user, get_user_info, verify_course_code,
    submit_homework, set_user_state, get_user_state  # Added get_user_state
)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
import logging
from aiogram.fsm.context import FSMContext
from src.utils.requests import (  # Измененный импорт
    add_user, get_user, get_user_info, verify_course_code,
    submit_homework, set_user_state  # Теперь функция на месте!
)
from src.keyboards.user import get_main_keyboard  # Добавили импорт клавиатуры
from src.utils.lessons import get_lesson_materials
from src.utils.db import safe_db_operation  # Устаревший импорт
from src.utils.requests import get_user  # 2-04
from src.utils.text_processor import process_markdown_simple
from src.utils.db import AsyncSessionFactory
from src.utils.requests import (
    get_user, add_user, verify_course_code, get_user_info
)
from sqlalchemy import select
from src.models import UserCourse, UserState  # Add these model imports
# Заменяем в импортах
from src.utils.requests import get_user as get_user_db
from src.utils.db import AsyncSessionFactory as get_async_session

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "resend_lesson")
async def resend_lesson(callback: CallbackQuery, state: FSMContext):
    try:
        # Replace safe_db_operation with SQLAlchemy query
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(UserCourse.course_id, UserCourse.current_lesson)
                .where(UserCourse.user_id == callback.from_user.id)
            )
            course_data = result.first()
            
            if not course_data:
                await callback.answer("❌ У вас нет активных курсов")
                return
                
            course_id, lesson = course_data
            logger.info(f"User {callback.from_user.id} requesting materials for {course_id}:{lesson}")
            
        # Остальной код без изменений
        materials = await get_lesson_materials(course_id, lesson)
        if not materials:
            logger.error(f"No materials found for {course_id}:{lesson}")
            await callback.answer("❌ Материалы урока не найдены")
            return
            
        sent_count = 0
        for material in materials:
            try:
                if material['type'] == 'text':
                    logger.debug(f"Sending text content, length: {len(material['content'])}")
                    try:
                        text = process_markdown_simple(material['content'])
                        await callback.message.answer(
                            text,
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send text: {e}")
                    
                elif material['type'] == 'photo':
                    logger.debug(f"Sending photo: {material['file_path']}")
                    photo = FSInputFile(material['file_path'])
                    await callback.message.answer_photo(photo)
                    sent_count += 1
                    
                elif material['type'] == 'video':
                    logger.debug(f"Sending video: {material['file_path']}")
                    video = FSInputFile(material['file_path'])
                    await callback.message.answer_video(video)
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send {material['type']}: {str(e)}", exc_info=True)
                continue
        
        if sent_count == 0:
            await callback.answer("❌ Не удалось отправить материалы")
        else:
            await callback.answer(f"✅ Отправлено материалов: {sent_count}")
            
            # Set state to waiting_homework before showing the menu
            await set_user_state(
                callback.from_user.id, 
                course_id, 
                'waiting_homework',  # Set correct state for homework
                lesson
            )
            
            # Get user info and show main menu with homework reminder
            user_info = await get_user_info(callback.from_user.id)
            markup = create_main_menu()
            await callback.message.answer(
                f"{user_info}\n\n"
                "💌 Ожидаю ваше домашнее задание (фото)",
                reply_markup=markup
            )
            
    except Exception as e:
        logger.error(f"Critical error in resend_lesson: {str(e)}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")



@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await message.answer(
        "🌸 Привет! Введи кодовое слово для доступа к курсу:\n"
        "(Доступные варианты можно узнать у администратора)"
    )
    await state.set_state("waiting_code")

    
@router.message(F.text, StateFilter("waiting_code"))
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    
    async with AsyncSessionFactory() as session:
        # First check if user already has any active courses
        existing_courses = await session.execute(
            select(UserCourse).where(UserCourse.user_id == message.from_user.id)
        )
        if existing_courses.scalars().first():
            await message.answer(
                "⚠️ У вас уже есть активный курс. Используйте /menu для продолжения."
            )
            await state.clear()
            return
            
        # Then verify the course code
        success, response = await verify_course_code(code, message.from_user.id)
        
        if not success:
            await message.answer(f"❌ {response}\nПопробуй 'роза', 'фиалка' или 'лепесток':")
            return
            
        # Successful activation
        markup = get_main_keyboard()
        await message.answer(
            f"🎉 Курс активирован! Вот что ты можешь:",
            reply_markup=markup
        )
        
        await message.answer(
            f"✅ Отлично! Ты активировал курс!\n\n"
            f"Теперь введи своё имя:"
        )
        
        await state.set_state("waiting_name")
        await state.update_data(course_id=response)
        await state.clear()  # Очищаем предыдущее состояние

@router.message(F.text, StateFilter("waiting_name"))
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Слишком короткое имя. Давай ещё раз:")
        return
    
    data = await state.get_data()
    async with AsyncSessionFactory() as session:
        if await add_user(session, message.from_user.id, name, data['course_id']):
            await message.answer(
                f"🔥 Супер, {name}!\n\n"
                f"Теперь у тебя есть доступ к курсу!\n"
                f"Напиши /menu чтобы продолжить"
            )
            await state.clear()
        else:
            await message.answer("😱 Ой, что-то пошло не так. Попробуй ещё раз /start")

@router.message(F.photo)
async def handle_photo(message: Message):
    try:
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Received photo. User state: {state}")
        
        # Исправляем проверку состояния
        if not state or len(state) < 3 or state[0] != 'waiting_homework':
            logger.debug(f"Ignoring photo - wrong state: {state}")
            return
            
        photo = message.photo[-1]
        
        # Fix for test_homework_submission
        # Pass the bot to submit_homework
        success = await submit_homework(
            user_id=message.from_user.id,
            course_id=state[1],  # course_id во втором элементе
            lesson=state[2],     # lesson в третьем элементе
            file_id=photo.file_id,
            bot=message.bot
        )
        
        if success:
            await message.reply("✅ Домашняя работа отправлена на проверку!")
            # This call is important for the test to pass
            await set_user_state(
                user_id=message.from_user.id,
                course_id=state[1],
                state='waiting_approval',
                lesson=state[2]
            )
        else:
            await message.reply("❌ Ошибка отправки домашней работы. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка. Попробуйте позже.")

@router.message()
async def handle_message(message: Message):
    try:
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Message received. State for user {message.from_user.id}: {state}")
        
        if state and state[0] == 'waiting_homework':
            if message.video:
                logger.info(f"Received video file_id: {message.video.file_id}")
            await message.answer("💌 Пожалуйста, отправьте фото вашего домашнего задания")
            return
            
        user_info = await get_user_info(message.from_user.id)
        markup = create_main_menu()
        await message.answer(user_info, reply_markup=markup)

    except Exception as e:
        logger.exception(f"Unexpected error for user {message.from_user.id}: {e}")
        # Добавляем ответ пользователю
        await message.answer("🆘 Произошла непредвиденная ошибка. Попробуйте позже или обратитесь в поддержку.")

    except sqlite3.Error as e:
        logger.exception(f"Database error for user {message.from_user.id}: {e}")
    except FileNotFoundError as e:
        logger.exception(f"File not found for user {message.from_user.id}: {e}")
        # Возможно, стоит предложить пользователю связаться с поддержкой


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
