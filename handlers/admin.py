from keyboards.admin import get_hw_review_kb

async def notify_admins(hw_id: int, user_id: int, file_id: str):
    admin_chat = os.getenv('ADMIN_GROUP')
    await bot.send_photo(
        admin_chat,
        file_id,
        caption=f"📝 Новая домашняя работа от пользователя {user_id}",
        reply_markup=get_hw_review_kb(hw_id)
    )


@router.callback_query(F.data.startswith("approve_"))
async def approve_homework(callback: CallbackQuery):
    hw_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE homeworks 
            SET status = 'approved', 
                admin_id = ?,
                approval_time = datetime('now')
            WHERE hw_id = ?
        ''', (callback.from_user.id, hw_id))
        
        # Award tokens
        await update_tokens(user_id, 10, "homework_approval")
        
    await callback.message.edit_text(f"✅ ДЗ #{hw_id} одобрено")