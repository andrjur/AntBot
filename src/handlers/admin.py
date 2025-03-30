from src.keyboards.admin import get_hw_review_kb
from src.utils.db import update_tokens
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import os
import logging
from src.utils.db import handle_homework_approval, DB_PATH, update_tokens
import aiosqlite

router = Router()

from aiogram import Bot

logger = logging.getLogger(__name__)

# Add bot instance
bot = Bot(token=os.getenv('BOT_TOKEN'))

async def notify_admins(hw_id: int, user_id: int, file_id: str):
    try:
        admin_chat = os.getenv('ADMIN_GROUP')
        await bot.send_photo(
            admin_chat,
            file_id,
            caption=f"📝 Новая домашняя работа от пользователя {user_id}",
            reply_markup=get_hw_review_kb(hw_id)
        )
    except Exception as e:
        logger.error(f"Failed to notify admins: {e}")

@router.callback_query(F.data.startswith("approve_"))
async def approve_homework(callback: CallbackQuery):
    try:
        hw_id = int(callback.data.split("_")[1])
        async with aiosqlite.connect(DB_PATH) as db:
            # Get user_id first
            cursor = await db.execute('SELECT user_id FROM homeworks WHERE hw_id = ?', (hw_id,))
            result = await cursor.fetchone()
            if not result:
                await callback.answer("❌ Homework not found")
                return
                
            user_id = result[0]
            
            # Update homework
            await db.execute('''
                UPDATE homeworks 
                SET status = 'approved', 
                    admin_id = ?,
                    approval_time = datetime('now'),
                    next_lesson_at = datetime('now', '+1 day')
                WHERE hw_id = ?
            ''', (callback.from_user.id, hw_id))
            await db.commit()
            
            # Award tokens
            await update_tokens(user_id, 10, "homework_approval")
            
            # Notify user
            await bot.send_message(
                user_id,
                "✅ Ваше домашнее задание принято!\n"
                "Следующий урок будет доступен через 24 часа от начала этого урока."
            )
            
            await callback.message.edit_text(f"✅ ДЗ #{hw_id} одобрено")
            
    except Exception as e:
        logger.error(f"Error in approve_homework: {e}")
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data.startswith("approve_homework_"))
async def approve_homework(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Update homework status
        await db.execute('''
            UPDATE homework 
            SET status = 'approved', 
                approved_at = CURRENT_TIMESTAMP,
                next_lesson_at = datetime(sent_at, '+1 day')
            WHERE user_id = ? AND status = 'pending'
        ''')
        await db.commit()
        
        # Notify user
        await bot.send_message(
            user_id,
            "✅ Ваше домашнее задание принято!\n"
            "Следующий урок будет доступен через 24 часа."
        )


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
async def approve_homework(callback: CallbackQuery, bot: Bot):
    try:
        # Parse callback data (hw_approve_userid_courseid_lesson)
        parts = callback.data.split("_")
        if len(parts) < 4:
            logger.error(f"Invalid callback data format: {callback.data}")
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        lesson = int(parts[4]) if len(parts) > 4 else None
        
        if not lesson:
            # Get lesson from database
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute('''
                    SELECT current_lesson 
                    FROM user_courses 
                    WHERE user_id = ? AND course_id = ?
                ''', (user_id, course_id))
                result = await cursor.fetchone()
                if not result:
                    await callback.answer("❌ Курс не найден", show_alert=True)
                    return
                lesson = result[0]
        
        # Handle approval
        success = await handle_homework_approval(
            user_id=user_id,
            course_id=course_id,
            lesson=lesson,
            status='approved',
            admin_id=callback.from_user.id
        )
        
        if success:
            # Award tokens
            await update_tokens(user_id, 10, "homework_approval")
            
            # Notify admin - use caption for photo messages
            original_text = callback.message.caption or callback.message.text or "Домашняя работа"
            new_text = f"{original_text}\n\n✅ Домашняя работа принята!"
            
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=new_text,
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    text=new_text,
                    reply_markup=None
                )
            
            # Notify user
            await bot.send_message(
                user_id,
                "✅ Ваша домашняя работа принята!\n"
                "Следующий урок будет доступен через 24 часа."
            )
        else:
            await callback.answer("❌ Ошибка при обработке", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in approve_homework: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("hw_reject_"))
async def reject_homework(callback: CallbackQuery, bot: Bot):
    # Similar structure as approve_homework
    try:
        parts = callback.data.split("_")
        if len(parts) != 4:
            logger.error(f"Invalid callback data format: {callback.data}")
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        user_id = int(parts[2])
        course_id = parts[3]
        
        # Get lesson from database
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('''
                SELECT current_lesson 
                FROM user_courses 
                WHERE user_id = ? AND course_id = ?
            ''', (user_id, course_id))
            result = await cursor.fetchone()
            if not result:
                await callback.answer("❌ Курс не найден", show_alert=True)
                return
            lesson = result[0]
        
        success = await handle_homework_approval(
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
        logger.error(f"Error in reject_homework: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)
