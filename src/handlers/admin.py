from src.keyboards.admin import get_hw_review_kb
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import os
import glob
import logging
from src.utils.db import DB_PATH,  safe_db_operation, get_courses_data, get_next_lesson, get_pending_homeworks
import aiosqlite
from src.config import get_lesson_delay, is_test_mode, TEST_MODE, extract_delay_from_filename
from datetime import datetime, timedelta  
import pytz


# Отключаем DEBUG логи для aiosqlite
logging.getLogger('aiosqlite').setLevel(logging.WARNING)

router = Router()

from aiogram import Bot

logger = logging.getLogger(__name__)


async def notify_admins(hw_id: int, user_id: int, file_id: str, bot: Bot):
    try:
        admin_chat = os.getenv('ADMIN_GROUP')
        if not admin_chat:
            raise ValueError("Admin group ID not configured")
            
        await bot.send_photo(
            admin_chat,
            file_id,
            caption=f"📝 Новая домашняя работа от пользователя {user_id}",
            reply_markup=get_hw_review_kb(hw_id)
        )
    except Exception as e:
        logger.error(f"9999 | Failed to notify admins: {e}")
        raise



@router.callback_query(F.data == "admin_test")
async def handle_admin_test(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "✅ Связь с админской группой подтверждена!\n"
            "Бот готов к работе."
        )
        await callback.answer()
        logger.info(f"1007 | Админ {callback.from_user.id} подтвердил работу бота")
    except Exception as e:
        logger.error(f"Error in admin test callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("hw_approve_"))
async def approve_homework(callback: CallbackQuery):
    try:
        user_id, course_id, lesson = parse_callback_data(callback.data)
        next_lesson = await get_next_lesson(user_id, course_id)
        
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz)
        
        # Calculate next lesson time
        result = await safe_db_operation(
            'SELECT datetime(?, "+" || ? || " seconds")',
            (current_time.strftime('%Y-%m-%d %H:%M:%S'), str(get_lesson_delay()))
        )
        next_time = await result.fetchone()
        
        if not next_time:
            logger.error("1002 | Failed to calculate next lesson time")
            return
            
        next_lesson_time = next_time[0]
        logger.info(f"1003 | Next lesson scheduled for: {next_lesson_time}")
        
        next_lesson = lesson + 1
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        base_path = os.path.join(project_root, 'data', 'courses', course_id, f'lesson{next_lesson}')
        
        if not os.path.exists(base_path):
            logger.error(f"1004 | Lesson directory not found: {base_path}")
            raise FileNotFoundError(f"1005 | Lesson {next_lesson} directory not found")
            
        lesson_files = glob.glob(os.path.join(base_path, '*.*'))
        logger.info(f"1006 | Found {len(lesson_files)} files in lesson {next_lesson}")
        
        for file_path in lesson_files:
            file_name = os.path.basename(file_path)
            delay = extract_delay_from_filename(file_name) 
            
            # Simply store course-relative path
            course_path = f"courses/{course_id}/lesson{next_lesson}/{file_name}"
            db_path = course_path.replace('\\', '/')
            
            logger.debug(f"1007 | Scheduling file: {db_path} with delay {delay}s")
            
            # Используем safe_db_operation для всех операций с БД
            await safe_db_operation('''
                INSERT INTO scheduled_files (user_id, course_id, lesson, file_name, send_at)
                VALUES (?, ?, ?, ?, datetime('now', '+' || ? || ' seconds'))
            ''', (user_id, course_id, next_lesson, db_path, str(delay)))
            
            # Обновляем статус домашки через safe_db_operation
            await safe_db_operation('''
                UPDATE homeworks 
                SET status = 'approved',
                    approval_time = datetime('now'),
                    next_lesson_at = ?
                WHERE user_id = ? AND course_id = ? AND lesson = ? AND status = 'pending'
            ''', (next_lesson_time, user_id, course_id, lesson))
            
            # И состояние пользователя тоже
            await safe_db_operation('''
                UPDATE user_states 
                SET current_state = 'waiting_next_lesson',
                    current_lesson = ?
                WHERE user_id = ?
            ''', (lesson + 1, user_id))
            
            # Уведомляем пользователя
            await callback.message.answer("✅ Домашняя работа принята! Следующий урок будет доступен позже.")
           
            logger.info(f"1008 | Database updated for user {user_id}, course {course_id}, lesson {lesson}")
                
    except Exception as e:
        logger.error(f"1009 | Error in approve_homework: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при проверке домашней работы")

@router.callback_query(F.data.startswith("hw_reject_"))
async def reject_homework(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split("_")
        if len(parts) != 4:
            logger.error("Invalid callback data format")
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        
        # Use safe_db_operation
        result = await safe_db_operation('''
            SELECT current_lesson 
            FROM user_courses 
            WHERE user_id = ? AND course_id = ?
        ''', (user_id, course_id))
        
        course_data = await result.fetchone()
        if not course_data:
            await callback.answer("❌ Курс не найден", show_alert=True)
            return
        
        lesson = course_data[0]  # Fix: Move this line before using lesson
        
        success = await process_homework_status(
            user_id=user_id,
            course_id=course_id,
            lesson=lesson,
            status='declined',
            admin_id=callback.from_user.id
        )
        
        if success:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Домашняя работа отклонена!"
            )
            
            await bot.send_message(
                user_id,
                "❌ Ваша домашняя работа отклонена.\n"
                "Пожалуйста, отправьте новое фото."
            )
        else:
            await callback.answer("❌ Ошибка при обработке", show_alert=True)
            
    except Exception as e:
        logger.error(f"24 Error in reject_homework: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(Command("progress", "status"))
async def show_progress(message: Message):
    try:
        result = await safe_db_operation('''
            SELECT us.current_lesson, us.current_state, 
                   c.course_name, h.next_lesson_at,
                   COUNT(CASE WHEN h.status = 'pending' THEN 1 END) as pending_hw
            FROM user_states us
            JOIN courses c ON us.course_id = c.course_id
            LEFT JOIN homeworks h ON us.user_id = h.user_id 
            WHERE us.user_id = ?
            GROUP BY us.user_id
        ''', (message.from_user.id,))
        
        user_id = message.from_user.id
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Get user's current course and lesson status
            cursor = await db.execute('''
                SELECT us.current_lesson, us.current_state, 
                       c.course_name, h.next_lesson_at,
                       COUNT(CASE WHEN h.status = 'pending' THEN 1 END) as pending_hw
                FROM user_states us
                JOIN courses c ON us.course_id = c.course_id
                LEFT JOIN homeworks h ON us.user_id = h.user_id 
                WHERE us.user_id = ?
                GROUP BY us.user_id
            ''', (user_id,))
            result = await cursor.fetchone()
            
            if not result:
                await message.answer("❌ У вас пока нет активного курса")
                return
                
            lesson, state, course_name, next_lesson, pending_hw = result
            
            # Format next lesson time
            next_lesson_text = "доступен" if state == 'active' else \
                             f"будет доступен {next_lesson}" if next_lesson else \
                             "ожидает проверки домашнего задания"
            
            await message.answer(
                f"📊 Ваш прогресс:\n\n"
                f"📚 Курс: {course_name}\n"
                f"📝 Текущий урок: {lesson}\n"
                f"📅 Следующий урок: {next_lesson_text}\n"
                f"📋 Непроверенных домашних заданий: {pending_hw}"
            )
            
    except Exception as e:
        logger.error(f"28 Error in progress command: {e}")
        await message.answer("❌ Не удалось получить информацию о прогрессе")


# Переименовываем функцию и исправляем параметры
async def process_homework_status(user_id: int, course_id: str, lesson: int, status: str, admin_id: int) -> bool:
    try:
        await safe_db_operation('''
            UPDATE homeworks 
            SET status = ?,
                admin_id = ?,
                approval_time = datetime('now')
            WHERE user_id = ? 
            AND course_id = ? 
            AND lesson = ?
            AND status = 'pending'
        ''', (status, admin_id, user_id, course_id, lesson))
        
        return True
        
    except Exception as e:
        logger.error(f"42 | Error processing homework status: {e}", exc_info=True)
        return False


@router.callback_query(F.data == "show_pending_hw")
async def show_pending_homeworks(callback: CallbackQuery):
    homeworks = await get_pending_homeworks()
    # Process homeworks...

# Add after imports
def parse_callback_data(callback_data: str) -> tuple[int, str, int]:
    """Parse callback data in format 'hw_approve_user_id_course_id_lesson'"""
    try:
        _, _, user_id, course_id, lesson = callback_data.split('_')
        return int(user_id), course_id, int(lesson)
    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse callback data: {callback_data}, error: {e}")
        raise ValueError(f"Invalid callback data format: {callback_data}")
