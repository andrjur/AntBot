@pytest.mark.asyncio
async def test_homework_approval():
    callback = AsyncMock(CallbackQuery)
    callback.data = "approve_hw_12345"
    
    await process_homework_approval(callback)
    
    # Verify user notification
    callback.bot.send_message.assert_called_with(
        chat_id=12345,
        text="✅ Ваше задание принято!"
    )
    
    # Verify next lesson scheduling
    next_lesson = await get_next_lesson_time(12345)
    assert next_lesson is not None

@pytest.mark.asyncio
async def test_statistics():
    stats = await get_course_statistics("femininity")
    assert "avg_homework_time" in stats
    assert "total_users" in stats
    assert "completion_rate" in stats