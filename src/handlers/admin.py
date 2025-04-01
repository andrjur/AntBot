from src.keyboards.admin import get_hw_review_kb
from aiogram import Router, F, Bot  # Added Bot to imports
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import os
import glob
import logging
from datetime import datetime
import pytz
from src.utils.db import DB_PATH, safe_db_operation, get_courses_data, get_next_lesson, get_pending_homeworks
from src.config import get_lesson_delay, is_test_mode, TEST_MODE, extract_delay_from_filename
from src.keyboards.user import get_main_keyboard  # Переносим импорт наверх
import logging
from src.utils.db import safe_db_operation

logger = logging.getLogger(__name__)
router = Router()  # Добавляем создание роутера
logger.info('3001 | handlers/admin.py роутер создан 🎮')

@router.callback_query(F.data == "admin_test")
async def handle_admin_test(callback: CallbackQuery):
    logger.info('3002 | Начинаем админ-тест 🎯')
    try:
        await callback.message.edit_text(
            "✅ Связь с админской группой подтверждена!\n"
            "Бот готов к работе."
        )
        await callback.answer()
        logger.info(f"3003 | Админ {callback.from_user.id} подтвердил работу бота 🎉")
    except Exception as e:
        logger.error(f"Error in admin test callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("hw_approve_"))
async def approve_homework(callback: CallbackQuery, bot: Bot):  # Добавляем bot в параметры
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
            delay = extract_delay_from_filename(file_name)  # This already handles test mode!
            
            # Simply store course-relative path
            course_path = f"courses/{course_id}/lesson{next_lesson}/{file_name}"
            db_path = course_path.replace('\\', '/')
            
            # In approve_homework function:
            # Simply store file name without path
            db_path = os.path.basename(file_name)
            
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
            # После цикла с файлами
            from src.keyboards.user import get_main_keyboard  # Добавить импорт вверху файла
            
            await bot.send_message(
                user_id,
                "✅ Домашняя работа принята! Следующий урок будет доступен позже.",
                reply_markup=get_main_keyboard()
            )
            logger.info(f"1008 | Homework approved for user {user_id}")
        logger.info(f"1008 | Database updated for user {user_id}, course {course_id}, lesson {lesson}")
                
    except Exception as e:
        logger.error(f"1009 | Error in approve_homework: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при проверке домашней работы")

@router.callback_query(F.data.startswith("hw_reject_"))
async def reject_homework(callback: CallbackQuery, bot):
    try:
        user_id, course_id, lesson = parse_callback_data(callback.data)
        # Убираем лишний отступ у этих строчек
        # logger.error("Invalid callback data format")
        # await callback.answer("❌ Неверный формат данных", show_alert=True)
        # return
        
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
        # Remove duplicate query
        # result = await safe_db_operation...
        
        user_id = message.from_user.id
        
        async with aiosqlite.connect(DB_PATH) as db:
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

@router.callback_query(F.data.startswith("view_hw_"))
async def show_other_homeworks(callback: CallbackQuery, bot: Bot):
    try:
        # Парсим course_id и lesson из callback_data
        _, course_id, lesson = callback.data.split('_')
        lesson = int(lesson)
        
        # Получаем все одобренные домашки по этому уроку
        result = await safe_db_operation('''
            SELECT h.file_id, h.user_id, h.approval_time
            FROM homeworks h
            WHERE h.course_id = ? 
            AND h.lesson = ?
            AND h.status = 'approved'
            ORDER BY h.approval_time DESC
            LIMIT 10
        ''', (course_id, lesson))
        
        homeworks = await result.fetchall()
        
        if not homeworks:
            await callback.answer("Пока нет одобренных работ по этому уроку 🤷‍♂️", show_alert=True)
            return
            
        await callback.answer()
        
        # Отправляем галерею работ
        for hw in homeworks:
            file_id, student_id, approved_at = hw
            caption = f"👤 Ученик: {student_id}\n📅 Одобрено: {approved_at}"
            try:
                await bot.send_photo(
                    callback.from_user.id,
                    file_id,
                    caption=caption
                )
            except Exception as e:
                logger.error(f"Error sending homework photo: {e}")
                continue
                
        await bot.send_message(
            callback.from_user.id,
            "✨ Это были последние одобренные работы по этому уроку!"
        )
        
    except Exception as e:
        logger.error(f"Error showing other homeworks: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке работ", show_alert=True)

def parse_callback_data(callback_data: str) -> tuple[int, str, int]:
    """Parse callback data in format 'hw_approve_user_id_course_id_lesson'"""
    try:
        _, _, user_id, course_id, lesson = callback_data.split('_')
        return int(user_id), course_id, int(lesson)
    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse callback data: {callback_data}, error: {e}")
        raise ValueError(f"Invalid callback data format: {callback_data}")


async def get_course_statistics(course_id: str) -> str:
    """Получаем статистику по курсу (для админов, которые любят цифры 📊)"""
    try:
        result = await safe_db_operation('''
            SELECT 
                COUNT(DISTINCT user_id) as total_users,
                AVG(current_lesson) as avg_lesson,
                MAX(current_lesson) as max_lesson
            FROM user_courses 
            WHERE course_id = ?
        ''', (course_id,), fetch_one=True)
        
        if not result:
            return "Статистика недоступна 📉"
            
        total, avg, max_lesson = result
        return f"""
Статистика по курсу:
👥 Всего учеников: {total}
📚 Средний урок: {round(avg, 1)}
🎯 Максимальный урок: {max_lesson}
"""
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return "Произошла ошибка при получении статистики 😢"


@router.message(Command("stats"))
async def show_course_stats(message: Message):
    """Показываем статистику по курсам 📊"""
    try:
        courses = get_courses_data()
        stats_text = "📊 Статистика по курсам:\n\n"
        
        for course_id in courses:
            course_stats = await get_course_statistics(course_id)
            stats_text += f"🎓 Курс {course_id}:\n{course_stats}\n"
            
        await message.answer(stats_text)
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await message.answer("❌ Не удалось получить статистику")
