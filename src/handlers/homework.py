from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
import logging
import os
import pytz
import random
from datetime import datetime
import glob
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.utils.db import (
    safe_db_operation, submit_homework, get_user_state, 
    set_user_state, get_next_lesson, get_admin_ids
)
from src.config import get_lesson_delay, extract_delay_from_filename
from src.keyboards.admin import get_hw_review_kb, get_rejection_reasons_kb
from src.keyboards.markup import create_main_menu

router = Router()
logger = logging.getLogger(__name__)

# Добавляем FSM для комментирования отказа
class RejectHomeworkStates(StatesGroup):
    waiting_for_comment = State()

@router.message(F.photo | F.document)
async def handle_homework(message: Message, bot: Bot):
    """Обработчик отправки домашнего задания (фото или документ)"""
    try:
        # Получаем текущее состояние пользователя
        state = await get_user_state(message.from_user.id)
        logger.debug(f"Получено домашнее задание. Состояние пользователя: {state}")
        
        # Проверяем, что пользователь находится в состоянии ожидания домашнего задания
        if not state or state[1] != 'waiting_homework':
            logger.debug(f"Игнорируем файл - неверное состояние: {state}")
            return
            
        # Получаем информацию о курсе и уроке
        course_id = state[0]
        current_lesson = state[2]
        
        # Получаем file_id в зависимости от типа сообщения
        if message.photo:
            file_id = message.photo[-1].file_id  # Берем последнее (самое качественное) фото
            file_type = 'photo'
        elif message.document:
            file_id = message.document.file_id
            file_type = 'document'
        else:
            await message.reply("❌ Пожалуйста, отправьте фото или документ для домашнего задания.")
            return
        
        # Отправляем домашнее задание на проверку
        hw_id = await submit_homework(
            user_id=message.from_user.id,
            course_id=course_id,
            lesson=current_lesson,
            file_id=file_id,
            bot=bot  # Передаем экземпляр бота
        )
        
        if hw_id:
            await message.reply("✅ Ваше домашнее задание отправлено на проверку! Мы сообщим вам, когда оно будет проверено.")
            
            # Меняем состояние пользователя на ожидание проверки
            await set_user_state(
                user_id=message.from_user.id,
                course_id=course_id,
                state='waiting_approval',
                lesson=current_lesson
            )
            
            # Пересылаем домашнее задание всем админам
            admin_ids = await get_admin_ids()
            
            # Формируем текст сообщения для админов
            admin_message = (
                f"📝 Новое домашнее задание!\n"
                f"👤 Пользователь: {message.from_user.full_name} (ID: {message.from_user.id})\n"
                f"📚 Курс: {course_id}\n"
                f"📖 Урок: {current_lesson}\n"
                f"🆔 ID задания: {hw_id}"
            )
            
            # Пересылаем фото или документ всем админам
            for admin_id in admin_ids:
                try:
                    if file_type == 'photo':
                        # Пересылаем фото с подписью
                        sent_message = await bot.send_photo(
                            chat_id=admin_id,
                            photo=file_id,
                            caption=admin_message
                        )
                    else:
                        # Пересылаем документ с подписью
                        sent_message = await bot.send_document(
                            chat_id=admin_id,
                            document=file_id,
                            caption=admin_message
                        )
                    
                    # Добавляем кнопки для одобрения/отклонения
                    await bot.send_message(
                        chat_id=admin_id,
                        text="Выберите действие:",
                        reply_markup=get_hw_review_kb(message.from_user.id, course_id, current_lesson)
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка при пересылке домашнего задания админу {admin_id}: {e}")
            
            # Показываем основное меню пользователю
            await message.answer(
                "Что вы хотите сделать дальше?", 
                reply_markup=create_main_menu(course_id)
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
        
        # Исправляем ошибку с fetchone для списка
        if result and len(result) > 0:
            next_time = result[0]
        else:
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
async def reject_homework_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало процесса отклонения домашнего задания с выбором причины"""
    try:
        # Извлекаем данные из callback_data (формат: hw_reject_USER_ID_COURSE_ID_LESSON)
        parts = callback.data.split('_')
        if len(parts) < 5:
            await callback.answer("❌ Неверный формат данных")
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        lesson = int(parts[4])
        
        # Сохраняем данные в FSM
        await state.update_data(
            reject_user_id=user_id,
            reject_course_id=course_id,
            reject_lesson=lesson
        )
        
        # Показываем клавиатуру с готовыми причинами отказа
        await callback.message.answer(
            "Выберите причину отказа или напишите свой комментарий:",
            reply_markup=get_rejection_reasons_kb()
        )
        
        # Устанавливаем состояние ожидания комментария
        await state.set_state(RejectHomeworkStates.waiting_for_comment)
        
        await callback.answer("Выберите причину отказа")
        
    except Exception as e:
        logger.error(f"Ошибка при начале отклонения домашнего задания: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(RejectHomeworkStates.waiting_for_comment, F.data.startswith("reject_reason_"))
async def process_rejection_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора готовой причины отказа"""
    try:
        # Получаем выбранную причину
        reason_key = callback.data.replace("reject_reason_", "")
        
        # Словарь с готовыми причинами и соответствующими картинками
        reasons = {
            "shy": {
                "text": "Ой, засмущала! 😳 Я не могу такое принять. Попробуйте сделать задание более скромно.",
                "image": "rejection_shy.jpg"
            },
            "communism": {
                "text": "Товарищ! Такими темпами коммунизм не построишь! 🚩 Старайтесь лучше!",
                "image": "rejection_communism.jpg"
            },
            "focus": {
                "text": "А ну-ка взяла... себя в руки! 💪 Сосредоточьтесь и сделайте задание более качественно.",
                "image": "rejection_focus.jpg"
            },
            "random": {
                "text": None,  # Будет выбрано случайно из файла
                "image": None  # Будет выбрано случайно из директории
            }
        }
        
        # Получаем данные из FSM
        data = await state.get_data()
        user_id = data.get("reject_user_id")
        course_id = data.get("reject_course_id")
        lesson = data.get("reject_lesson")
        
        # Если выбрана случайная причина, выбираем из файла
        comment_text = reasons.get(reason_key, {}).get("text")
        if reason_key == "random" or not comment_text:
            # Путь к файлу с мотивирующими фразами
            phrases_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "rejection_phrases.txt"
            )
            
            try:
                with open(phrases_path, "r", encoding="utf-8") as f:
                    phrases = f.readlines()
                    comment_text = random.choice([p.strip() for p in phrases if p.strip()])
            except Exception as e:
                logger.error(f"Ошибка при чтении фраз отказа: {e}")
                comment_text = "Пожалуйста, доработайте задание и отправьте снова."
        
        # Отклоняем домашнее задание с комментарием
        await reject_homework_with_comment(
            user_id=user_id,
            course_id=course_id,
            lesson=lesson,
            admin_id=callback.from_user.id,
            comment=comment_text,
            image_key=reasons.get(reason_key, {}).get("image"),
            callback=callback,
            bot=bot
        )
        
        # Сбрасываем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке причины отказа: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")
        await state.clear()


@router.message(RejectHomeworkStates.waiting_for_comment)
async def process_custom_rejection_comment(message: Message, state: FSMContext, bot: Bot):
    """Обработка пользовательского комментария для отказа"""
    try:
        # Получаем данные из FSM
        data = await state.get_data()
        user_id = data.get("reject_user_id")
        course_id = data.get("reject_course_id")
        lesson = data.get("reject_lesson")
        
        # Получаем текст комментария
        comment = message.text
        
        if not comment:
            await message.reply("Пожалуйста, введите комментарий или выберите готовую причину.")
            return
        
        # Отклоняем домашнее задание с комментарием
        await reject_homework_with_comment(
            user_id=user_id,
            course_id=course_id,
            lesson=lesson,
            admin_id=message.from_user.id,
            comment=comment,
            image_key=None,  # Без картинки для пользовательского комментария
            callback=None,
            message=message,
            bot=bot
        )
        
        # Сбрасываем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке пользовательского комментария: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при отклонении домашнего задания")
        await state.clear()


async def reject_homework_with_comment(user_id, course_id, lesson, admin_id, comment, image_key=None, 
                                      callback=None, message=None, bot=None):
    """Функция для отклонения домашнего задания с комментарием и картинкой"""
    try:
        # Устанавливаем московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz)
        
        # Обновляем статус домашнего задания с комментарием
        await safe_db_operation(
            '''
            UPDATE homeworks
            SET status = 'rejected', 
                approval_time = ?,
                admin_id = ?,
                admin_comment = ?
            WHERE user_id = ? AND course_id = ? AND lesson = ? AND status = 'pending'
            ''',
            (current_time.strftime('%Y-%m-%d %H:%M:%S'), 
             admin_id, comment, user_id, course_id, lesson)
        )
        
        # Подготавливаем сообщение для пользователя
        user_message = f"❌ Ваше домашнее задание по уроку {lesson} требует доработки.\n\n"
        user_message += f"💬 Комментарий: {comment}\n\n"
        user_message += "Пожалуйста, отправьте исправленное задание."
        
        # Если есть ключ картинки, отправляем её
        if image_key:
            # Путь к директории с картинками отказов
            images_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "images", "rejections"
            )
            
            # Если выбрана случайная картинка
            if image_key == "random":
                try:
                    # Создаем директорию, если она не существует
                    if not os.path.exists(images_dir):
                        os.makedirs(images_dir)
                        logger.info(f"Создана директория для картинок отказов: {images_dir}")
                    
                    images = [f for f in os.listdir(images_dir) 
                             if os.path.isfile(os.path.join(images_dir, f)) 
                             and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    if images:
                        image_key = random.choice(images)
                    else:
                        image_key = None
                except Exception as e:
                    logger.error(f"Ошибка при выборе случайной картинки: {e}")
                    image_key = None
            
            # Отправляем картинку с подписью
            if image_key:
                image_path = os.path.join(images_dir, image_key)
                if os.path.exists(image_path):
                    photo = FSInputFile(image_path)
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption=user_message
                    )
                else:
                    # Если картинка не найдена, отправляем только текст
                    await bot.send_message(
                        chat_id=user_id,
                        text=user_message
                    )
            else:
                # Если ключ картинки не определен, отправляем только текст
                await bot.send_message(
                    chat_id=user_id,
                    text=user_message
                )
        else:
            # Если картинка не требуется, отправляем только текст
            await bot.send_message(
                chat_id=user_id,
                text=user_message
            )
        
        # Обновляем состояние пользователя
        await set_user_state(
            user_id=user_id,
            course_id=course_id,
            state='waiting_homework',
            lesson=lesson
        )
        
        # Показываем основное меню пользователю
        await bot.send_message(
            chat_id=user_id,
            text="Что вы хотите сделать дальше?",
            reply_markup=create_main_menu(course_id)
        )
        
        # Обновляем сообщение с клавиатурой, если есть callback
        if callback and callback.message:
            await callback.message.edit_text(
                f"❌ Домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson} отклонено.\n"
                f"💬 Комментарий: {comment}",
                reply_markup=None
            )
            await callback.answer("✅ Домашнее задание отклонено с комментарием")
        
        # Отправляем подтверждение, если есть message
        if message:
            await message.reply(
                f"✅ Домашнее задание пользователя {user_id} по курсу {course_id}, урок {lesson} отклонено с комментарием."
            )
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении домашнего задания с комментарием: {e}", exc_info=True)
        if callback:
            await callback.answer("❌ Произошла ошибка при отклонении домашнего задания")
        if message:
            await message.reply("❌ Произошла ошибка при отклонении домашнего задания")


# Добавляем функцию для просмотра домашних заданий других пользователей
@router.callback_query(F.data.startswith("view_homeworks_"))
async def view_other_homeworks(callback: CallbackQuery, bot: Bot):
    """Просмотр домашних заданий других пользователей"""
    try:
        # Извлекаем данные из callback_data (формат: view_homeworks_COURSE_ID_LESSON)
        parts = callback.data.split('_')
        if len(parts) < 4:
            await callback.answer("❌ Неверный формат данных")
            return
            
        course_id = parts[2]
        lesson = int(parts[3])
        
        # Получаем список одобренных домашних заданий для данного курса и урока
        result = await safe_db_operation(
            '''
            SELECT h.user_id, h.file_id, u.name
            FROM homeworks h
            JOIN users u ON h.user_id = u.user_id
            WHERE h.course_id = ? AND h.lesson = ? AND h.status = 'approved'
            ORDER BY h.approval_time DESC
            LIMIT 10
            ''',
            (course_id, lesson)
        )
        
        if not result or len(result) == 0:
            await callback.answer("Нет доступных домашних заданий для просмотра")
            return
            
        await callback.answer("Загружаем домашние задания...")
        
        # Отправляем сообщение с информацией
        await callback.message.answer(
            f"📚 Примеры домашних заданий по курсу {course_id}, урок {lesson}:\n"
            f"Всего найдено: {len(result)} заданий"
        )
        
        # Отправляем каждое домашнее задание
        for hw in result:
            user_id, file_id, user_name = hw
            
            try:
                # Отправляем фото с подписью
                await bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=file_id,
                    caption=f"👤 Автор: {user_name}\n📖 Урок: {lesson}"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке домашнего задания {file_id}: {e}")
                # Пробуем отправить как документ, если не удалось как фото
                try:
                    await bot.send_document(
                        chat_id=callback.from_user.id,
                        document=file_id,
                        caption=f"👤 Автор: {user_name}\n📖 Урок: {lesson}"
                    )
                except Exception as e2:
                    logger.error(f"Ошибка при отправке документа {file_id}: {e2}")
        
        # Показываем основное меню
        await callback.message.answer(
            "Что вы хотите сделать дальше?",
            reply_markup=create_main_menu(course_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре домашних заданий: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при загрузке домашних заданий")