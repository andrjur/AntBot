from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
import logging
import os
import pytz
from datetime import datetime
import glob

from src.utils.db import (
    safe_db_operation, submit_homework, get_user_state, 
    set_user_state, get_next_lesson
)
from src.config import get_lesson_delay, extract_delay_from_filename
from src.keyboards.admin import get_hw_review_kb

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.photo | F.document)
async def handle_homework(message: Message, bot: Bot):
    """Обработчик отправки домашнего задания (фото или документ)"""
    try:
        # Получаем текущее состояние пользователя
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Получено домашнее задание. Состояние пользователя: {state}")
        
        # Проверяем, что пользователь находится в состоянии ожидания домашнего задания
        if not state or state[0] != 'waiting_homework':
            logger.debug(f"Игнорируем файл - неверное состояние: {state}")
            return
            
        # Получаем информацию о курсе и уроке
        course_id = state[1]
        current_lesson = state[2]
        
        # Получаем file_id в зависимости от типа сообщения
        if message.photo:
            file_id = message.photo[-1].file_id  # Берем последнее (самое качественное) фото
        elif message.document:
            file_id = message.document.file_id
        else:
            await message.reply("❌ Пожалуйста, отправьте фото или документ для домашнего задания.")
            return
        
        # Отправляем домашнее задание на проверку
        success = await submit_homework(
            user_id=message.from_user.id,
            course_id=course_id,
            lesson=current_lesson,
            file_id=file_id,
            bot=bot  # Передаем экземпляр бота
        )
        
        if success:
            await message.reply("✅ Ваше домашнее задание отправлено на проверку! Мы сообщим вам, когда оно будет проверено.")
            
            # Меняем состояние пользователя на ожидание проверки
            await set_user_state(
                user_id=message.from_user.id,
                course_id=course_id,
                state='waiting_approval',
                lesson=current_lesson
            )
        else:
            await message.reply("❌ Произошла ошибка при отправке домашнего задания. Пожалуйста, попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке домашнего задания: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")


@router.callback_query(F.data.startswith("hw_approve_"))
async def approve_homework(callback: CallbackQuery, bot: Bot):
    """Обработчик подтверждения домашнего задания администратором"""
    try:
        # Извлекаем данные из callback_data (формат: hw_approve_USER_ID_COURSE_ID_LESSON)
        parts = callback.data.split('_')
        if len(parts) < 5:
            await callback.answer("❌ Неверный формат данных")
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        lesson = int(parts[4])
        
        logger.info(f"Админ {callback.from_user.id} одобряет домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson}")
        
        # Получаем следующий урок
        next_lesson = lesson + 1
        
        # Устанавливаем московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz)
        
        # Рассчитываем время следующего урока
        delay = get_lesson_delay()
        result = await safe_db_operation(
            'SELECT datetime(?, "+" || ? || " seconds")',
            (current_time.strftime('%Y-%m-%d %H:%M:%S'), str(delay))
        )
        next_time = result[0] if result else None
        
        if not next_time:
            logger.error("❌ Не удалось рассчитать время следующего урока")
            await callback.answer("❌ Ошибка при расчете времени следующего урока")
            return
            
        next_lesson_time = next_time[0]
        logger.info(f"Следующий урок запланирован на: {next_lesson_time}")
        
        # Проверяем существование директории следующего урока
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        base_path = os.path.join(project_root, 'data', 'courses', course_id, f'lesson{next_lesson}')
        
        if not os.path.exists(base_path):
            logger.warning(f"Директория урока {next_lesson} не найдена: {base_path}")
            await callback.answer(f"⚠️ Урок {next_lesson} не найден, но домашнее задание принято")
        else:
            # Находим файлы для следующего урока
            lesson_files = glob.glob(os.path.join(base_path, '*.*'))
            logger.info(f"Найдено {len(lesson_files)} файлов в уроке {next_lesson}")
            
            # Планируем отправку файлов
            for file_path in lesson_files:
                file_name = os.path.basename(file_path)
                delay = extract_delay_from_filename(file_name)
                
                # Сохраняем только имя файла без пути
                await safe_db_operation(
                    '''
                    INSERT INTO scheduled_files 
                    (user_id, course_id, lesson, file_name, send_at)
                    VALUES (?, ?, ?, ?, datetime(?, "+" || ? || " seconds"))
                    ''',
                    (user_id, course_id, next_lesson, file_name, 
                     current_time.strftime('%Y-%m-%d %H:%M:%S'), str(delay))
                )
        
        # Обновляем статус домашнего задания
        await safe_db_operation(
            '''
            UPDATE homeworks
            SET status = 'approved', 
                approval_time = ?,
                next_lesson_at = ?,
                admin_id = ?
            WHERE user_id = ? AND course_id = ? AND lesson = ? AND status = 'pending'
            ''',
            (current_time.strftime('%Y-%m-%d %H:%M:%S'), 
             next_lesson_time, callback.from_user.id, 
             user_id, course_id, lesson)
        )
        
        # Обновляем текущий урок пользователя
        await safe_db_operation(
            '''
            UPDATE user_courses
            SET current_lesson = ?
            WHERE user_id = ? AND course_id = ?
            ''',
            (next_lesson, user_id, course_id)
        )
        
        # Уведомляем пользователя об одобрении домашнего задания
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ Ваше домашнее задание по уроку {lesson} одобрено! Следующий урок будет отправлен {next_lesson_time}."
        )
        
        # Обновляем состояние пользователя
        await set_user_state(
            user_id=user_id,
            course_id=course_id,
            state='waiting_lesson',
            lesson=next_lesson
        )
        
        # Обновляем сообщение с клавиатурой
        await callback.message.edit_text(
            f"✅ Домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson} одобрено!\n"
            f"Следующий урок {next_lesson} запланирован на {next_lesson_time}.",
            reply_markup=None
        )
        
        await callback.answer("✅ Домашнее задание одобрено!")
        
    except Exception as e:
        logger.error(f"Ошибка при одобрении домашнего задания: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при одобрении домашнего задания")


@router.callback_query(F.data.startswith("hw_reject_"))
async def reject_homework(callback: CallbackQuery, bot: Bot):
    """Обработчик отклонения домашнего задания администратором"""
    try:
        # Извлекаем данные из callback_data (формат: hw_reject_USER_ID_COURSE_ID_LESSON)
        parts = callback.data.split('_')
        if len(parts) < 5:
            await callback.answer("❌ Неверный формат данных")
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        lesson = int(parts[4])
        
        logger.info(f"Админ {callback.from_user.id} отклоняет домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson}")
        
        # Обновляем статус домашнего задания
        await safe_db_operation(
            '''
            UPDATE homeworks
            SET status = 'rejected', 
                approval_time = ?,
                admin_id = ?
            WHERE user_id = ? AND course_id = ? AND lesson = ? AND status = 'pending'
            ''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
             callback.from_user.id, user_id, course_id, lesson)
        )
        
        # Уведомляем пользователя об отклонении домашнего задания
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Ваше домашнее задание по уроку {lesson} требует доработки. Пожалуйста, отправьте исправленное задание."
        )
        
        # Обновляем состояние пользователя
        await set_user_state(
            user_id=user_id,
            course_id=course_id,
            state='waiting_homework',
            lesson=lesson
        )
        
        # Обновляем сообщение с клавиатурой
        await callback.message.edit_text(
            f"❌ Домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson} отклонено.",
            reply_markup=None
        )
        
        await callback.answer("❌ Домашнее задание отклонено")
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении домашнего задания: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при отклонении домашнего задания")