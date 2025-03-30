import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')

async def forward_homework_to_admins(message, user_info):
    """Forward homework to admin group with approval buttons"""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"hw_approve_{message.from_user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"hw_decline_{message.from_user.id}")
            ]
        ])
        
        caption = (f"📚 Домашнее задание\n"
                  f"От: {user_info['name']}\n"
                  f"Курс: {user_info['course']}\n"
                  f"Урок: {user_info['lesson']}")
        
        if message.photo:
            logger.info(f"Forwarding homework photo from user {message.from_user.id}")
            await message.bot.send_photo(
                chat_id=ADMIN_GROUP_ID,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=keyboard
            )
        elif message.video:
            logger.info(f"Forwarding homework video from user {message.from_user.id}")
            await message.bot.send_video(
                chat_id=ADMIN_GROUP_ID,
                video=message.video.file_id,
                caption=caption,
                reply_markup=keyboard
            )
        elif message.document:
            logger.info(f"Forwarding homework document from user {message.from_user.id}")
            await message.bot.send_document(
                chat_id=ADMIN_GROUP_ID,
                document=message.document.file_id,
                caption=caption,
                reply_markup=keyboard
            )
            
        logger.info(f"Homework forwarded to admin group for user {message.from_user.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to forward homework: {str(e)}", exc_info=True)
        return False