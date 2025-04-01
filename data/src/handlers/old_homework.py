@router.message(F.photo | F.document)
async def handle_homework(message: Message, bot: Bot):
    # ... existing code ...
    
    success = await submit_homework(
        user_id=message.from_user.id,
        course_id=course_id,
        lesson=current_lesson,
        file_id=file_id,
        bot=bot  # Pass the bot instance
    )
    
  