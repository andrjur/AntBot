import re
import json
import aiosqlite
import aiofiles  # Changed this line
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
import logging
from aiogram.fsm.context import FSMContext
from src.utils.db import add_user, get_user, get_user_info, verify_course_code, DB_PATH
from src.keyboards.markup import create_main_menu
from src.utils.lessons import get_lesson_materials
from aiogram.types import FSInputFile
from src.utils.text_processor import process_markdown

router = Router()

# Remove these duplicate imports
# from aiofiles import aiofiles  <- Remove this line
# from src.utils.lessons import get_lesson_materials  <- Remove this line

from src.utils.lessons import get_lesson_materials

logger = logging.getLogger(__name__)

@router.callback_query(F.data == "resend_lesson")
async def resend_lesson(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"Resend lesson requested. User: {callback.from_user.id}, State: {current_state}")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('''
                SELECT course_id, current_lesson
                FROM user_courses
                WHERE user_id = ?
            ''', (callback.from_user.id,))
            course_data = await cursor.fetchone()
            
        if not course_data:
            logger.warning(f"No active course for user {callback.from_user.id}")
            await callback.answer("❌ У вас нет активных курсов")
            return
            
        course_id, lesson = course_data
        logger.info(f"User {callback.from_user.id} requesting materials for {course_id}:{lesson}")
        
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
                        text = process_markdown(material['content'])
                        # Try multiple formatting options if one fails
                        for parse_mode in [None, 'HTML', 'MarkdownV2']:
                            try:
                                await callback.message.answer(
                                    text,
                                    parse_mode=parse_mode
                                )
                                sent_count += 1
                                break  # If successful, stop trying other modes
                            except Exception as e:
                                logger.debug(f"Failed to send with {parse_mode}: {e}")
                                continue
                    except Exception as e:
                        logger.error(f"Failed to send text: {e}")
                
                elif material['type'] == 'photo':
                    try:
                        photo = FSInputFile(material['file_path'])
                        await callback.message.answer_photo(photo)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send photo: {e}")
                        # Try alternative method if first fails
                        try:
                            with open(material['file_path'], 'rb') as photo:
                                await callback.message.answer_photo(photo)
                                sent_count += 1
                        except Exception as e2:
                            logger.error(f"Alternative photo send failed: {e2}")
                
                elif material['type'] == 'video':
                    logger.debug(f"Sending video: {material['file_path']}")
                    video = FSInputFile(material['file_path'])
                    await callback.message.answer_video(video)
                    
            except Exception as e:
                logger.error(f"Failed to send {material['type']}: {str(e)}", exc_info=True)
                continue
        
        if sent_count == 0:
            await callback.answer("❌ Не удалось отправить материалы")
        else:
            await callback.answer(f"✅ Отправлено материалов: {sent_count}")
            
    except Exception as e:
        logger.error(f"Critical error in resend_lesson: {str(e)}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    if not await get_user(message.from_user.id):
        await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя:")
        await state.set_state("registration")
        return
        
    # Check if user has active course
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT course_id FROM user_courses 
            WHERE user_id = ?
        ''', (message.from_user.id,))
        has_course = await cursor.fetchone()
    
    if not has_course:
        await state.set_state("activation")
        await message.answer("Введите кодовое слово для активации курса:")
        return
        
    user_info = await get_user_info(message.from_user.id)
    markup = create_main_menu()
    await message.answer(user_info, reply_markup=markup)

@router.message(F.text, StateFilter("registration"))
async def process_registration(message: Message, state: FSMContext):
    # Just save the name, no phone number required
    await add_user(message.from_user.id, message.text)
    await state.clear()
    await message.answer("Регистрация завершена! Введите кодовое слово для активации курса:")

@router.message(F.text, StateFilter("activation"))
async def process_activation(message: Message, state: FSMContext):
    success, course_id = await verify_course_code(message.text, message.from_user.id)
    if success:
        with open('data/courses.json', 'r', encoding='utf-8') as f:
            courses = json.load(f)
        course = courses[course_id]
        
        await state.clear()
        await message.answer(
            f"✅ Активирован курс '{course['name']}'\n\n"
            "Можете приступать к обучению!"
        )
        
        # Show main menu after activation
        user_info = await get_user_info(message.from_user.id)
        markup = create_main_menu()
        await message.answer(user_info, reply_markup=markup)
    else:
        await message.answer("❌ Неверное кодовое слово. Попробуйте еще раз:")