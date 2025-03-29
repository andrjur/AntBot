import re
import json
import aiosqlite
import aiofiles  # Changed this line
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from src.utils.db import add_user, get_user, get_user_info, verify_course_code, DB_PATH
from src.keyboards.markup import create_main_menu
from src.utils.lessons import get_lesson_materials
from aiogram.types import FSInputFile

router = Router()

# Remove these duplicate imports
# from aiofiles import aiofiles  <- Remove this line
# from src.utils.lessons import get_lesson_materials  <- Remove this line

from src.utils.lessons import get_lesson_materials

@router.callback_query(F.data == "resend_lesson")
async def resend_lesson(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT course_id, current_lesson
            FROM user_courses
            WHERE user_id = ?
        ''', (callback.from_user.id,))
        course_data = await cursor.fetchone()
        
    if not course_data:
        await callback.answer("❌ У вас нет активных курсов")
        return
        
    course_id, lesson = course_data
    
    # Get lesson materials
    materials = await get_lesson_materials(course_id, lesson)
    
    for material in materials:
        if material['type'] == 'text':
            await callback.message.answer(material['content'])
        elif material['type'] == 'photo':
            photo = FSInputFile(material['file_path'])
            await callback.message.answer_photo(photo)
        elif material['type'] == 'video':
            video = FSInputFile(material['file_path'])
            await callback.message.answer_video(video)
    
    await callback.answer("✅ Материалы урока отправлены")

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