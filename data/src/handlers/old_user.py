from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
import logging
from aiogram.fsm.context import FSMContext
import sqlite3
from src.utils.db import (
    add_user, get_user, get_user_info, verify_course_code, 
    DB_PATH, get_user_state, submit_homework, set_user_state,
    safe_db_operation, get_courses_data  # Added these
)
from src.keyboards.markup import create_main_menu
from src.utils.lessons import get_lesson_materials
from src.utils.text_processor import process_markdown_simple

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "resend_lesson")
async def resend_lesson(callback: CallbackQuery, state: FSMContext):
    try:
        result = await safe_db_operation('''
            SELECT course_id, current_lesson
            FROM user_courses
            WHERE user_id = ?
        ''', (callback.from_user.id,))
        course_data = await result.fetchone()
        
        if not course_data:
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
            #await set_course_state(
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
    if not await get_user(message.from_user.id):
        await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя:")
        await state.set_state("registration")
        return
        
    try:
        result = await safe_db_operation('''
            SELECT course_id FROM user_courses 
            WHERE user_id = ?
        ''', (message.from_user.id,))
        has_course = await result.fetchone()
        
        if not has_course:
            await state.set_state("activation")
            await message.answer("Введите кодовое слово для активации курса:")
            return
            
        user_info = await get_user_info(message.from_user.id)
        markup = create_main_menu()
        await message.answer(user_info, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.message(F.text, StateFilter("registration"))
async def process_registration(message: Message, state: FSMContext):
    # Just save the name, no phone number required
    await add_user(message.from_user.id, message.text)
    await state.clear()
    await message.answer("Регистрация завершена! Введите кодовое слово для активации курса:")

@router.message(F.text, StateFilter("activation"))
async def process_activation(message: Message, state: FSMContext):
    try:
        success, course_id = await verify_course_code(message.text, message.from_user.id)
        
        if success:
            courses = get_courses_data()
            course = courses[course_id]
            
            # Send first lesson materials
            materials = await get_lesson_materials(course_id, 1)
            if materials:
                await message.answer(f"✅ Активирован курс '{course['name']}'")
                
                for material in materials:
                    try:
                        if material['type'] == 'text':
                            # Use HTML instead of Markdown for better compatibility
                            text = material['content'].replace('*', '<b>').replace('_', '<i>')
                            await message.answer(text, parse_mode='HTML')
                        elif material['type'] == 'photo':
                            photo = FSInputFile(material['file_path'])
                            await message.answer_photo(photo)
                        elif material['type'] == 'video':
                            video = FSInputFile(material['file_path'])
                            await message.answer_video(video)
                    except Exception as e:
                        logger.error(f"Error sending material: {e}", exc_info=True)
                        continue
                        
                await message.answer("✨ Материалы урока отправлены!")
            else:
                await message.answer("❌ Материалы урока не найдены")
        else:
            await message.answer("❌ Неверный код активации. Попробуйте еще раз:")
            
    except Exception as e:
        logger.error(f"116 Error in process_activation: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при активации курса. Попробуйте еще раз:")

@router.message(F.photo)
async def handle_photo(message: Message):
    try:
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Received photo. User state: {state}")
        
        # State tuple is (course_id, state, lesson)
        if not state or state[1] != 'waiting_homework':  # Changed from state[0]
            logger.debug(f"Ignoring photo - wrong state: {state}")
            return
            
        photo = message.photo[-1]
        success = await submit_homework(
            user_id=message.from_user.id,
            course_id=state[0],  # Changed from state[1]
            lesson=state[2],
            file_id=photo.file_id,
            bot=message.bot
        )
        
        if success:
            await message.reply("✅ Домашняя работа отправлена на проверку!")
            await set_user_state(
                user_id=message.from_user.id,
                state='waiting_approval',
                course_id=state[0],  # Changed from state[1]
                lesson=state[2]
            )
        else:
            await message.reply("❌ Ошибка отправки домашней работы. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка. Попробуйте позже.")


        state = await get_user_state(message.from_user.id)
        logger.debug(f"Message received. State for user {message.from_user.id}: {state}")
        
        if state and state[0] == 'waiting_homework':
            if message.video:
                logger.info(f"119 Received video file_id: {message.video.file_id}")
            await message.answer("💌 Пожалуйста, отправьте фото вашего домашнего задания")
            return
            

@router.message()
async def handle_message(message: Message):
    try:
        # Get current state
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Message received. State for user {message.from_user.id}: {state}")
        
        if state and state[0] == 'waiting_homework':
            if message.video:
                logger.info(f"119 Received video file_id: {message.video.file_id}")
            await message.answer("💌 Пожалуйста, отправьте фото вашего домашнего задания")
            return
            
        # Show main menu for any other messages
        user_info = await get_user_info(message.from_user.id)
        markup = create_main_menu()
        await message.answer(user_info, reply_markup=markup)

    except sqlite3.Error as e:
        logger.exception(f"Database error for user {message.from_user.id}: {e}")
    except FileNotFoundError as e:
        logger.exception(f"File not found for user {message.from_user.id}: {e}")
        # Возможно, стоит предложить пользователю связаться с поддержкой
    except Exception as e:
        logger.exception(f"Unexpected error for user {message.from_user.id}: {e}")
        # Возможно, стоит предложить пользователю связаться с поддержкой
