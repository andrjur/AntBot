async def notify_admins(course_id: str, user_id: int, lesson: int):
    try:
        # Получаем список админов
        admins = await get_admins()
        
        # Формируем сообщение
        user = await get_user(user_id)
        course = await get_course(course_id)
        
        text = (
            f"📬 Новое ДЗ на проверку!\n\n"
            f"👤 Ученик: {user.name}\n"
            f"🎓 Курс: {course.name}\n"
            f"📚 Урок: {lesson}\n"
            f"🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        
        # Отправляем каждому админу
        for admin in admins:
            try:
                await bot.send_message(
                    admin.user_id,
                    text,
                    reply_markup=get_hw_review_kb(user_id, course_id, lesson)
                )
            except Exception as e:
                logging.error(f"Не удалось уведомить админа {admin.user_id}: {e}")
                
    except Exception as e:
        logging.error(f"Ошибка уведомления админов: {e}")