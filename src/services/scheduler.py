from datetime import datetime, timedelta
import logging
from aiogram import Bot
from ..utils.session import AsyncSessionFactory
from ..models import ScheduledFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = AsyncIOScheduler()
bot = None  # Will be set during initialization

def init_scheduler(bot_instance: Bot):
    global bot
    bot = bot_instance
    scheduler.start()

async def schedule_lessons():
    """Schedule lessons for users"""
    logger.info("Scheduling lessons...")
    # Implementation here


async def schedule_next_lesson(user_id: int, course_id: str, lesson_num: int):
    try:
        # Проверяем, существует ли урок
        if not await lesson_exists(course_id, lesson_num):
            await bot.send_message(
                user_id,
                "🎉 Поздравляю! Ты завершил этот курс!"
            )
            return
            
        # Рассчитываем время отправки
        delay = await get_course_delay(course_id)  # Берём из настроек курса
        send_time = datetime.now() + timedelta(hours=delay)
        
        # Записываем в БД
        async with AsyncSessionFactory() as session:
            scheduled = ScheduledFile(
                user_id=user_id,
                course_id=course_id,
                lesson_num=lesson_num,
                send_time=send_time,
                status="pending"
            )
            session.add(scheduled)
            await session.commit()
            
        # Ставим в реальный планировщик
        scheduler.add_job(
            send_lesson,
            'date',
            run_date=send_time,
            args=[user_id, course_id, lesson_num],
            id=f"lesson_{user_id}_{course_id}_{lesson_num}"
        )
        
    except Exception as e:
        logging.error(f"Ошибка планирования урока: {e}")
        await bot.send_message(
            user_id,
            "⚠️ Не удалось запланировать следующий урок. Обратитесь в поддержку."
        )


async def send_lesson(user_id: int, course_id: str, lesson_num: int):
    try:
        # Получаем данные урока
        lesson_data = await get_lesson_data(course_id, lesson_num)
        
        # Отправляем разными сообщениями для стабильности
        if lesson_data.text:
            await bot.send_message(user_id, lesson_data.text)
        
        if lesson_data.photo:
            await bot.send_photo(user_id, FSInputFile(lesson_data.photo))
            
        if lesson_data.document:
            await bot.send_document(user_id, FSInputFile(lesson_data.document))
            
        # Обновляем прогресс
        async with AsyncSessionFactory() as session:
            await update_user_progress(session, user_id, course_id, lesson_num)
            
    except Exception as e:
        logging.error(f"Ошибка отправки урока {lesson_num} для {user_id}: {e}")
        await bot.send_message(
            user_id, 
            "📛 Упс, урок застрял в пути! Попробуй запросить его снова через меню."
        )