from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

async def schedule_lessons():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT user_id, course_id, current_lesson 
            FROM user_courses 
            WHERE next_lesson_at <= datetime('now')
        ''')
        for row in await cursor.fetchall():
            user_id, course_id, lesson = row
            await send_lesson(user_id, course_id, lesson)
            
scheduler.add_job(schedule_lessons, 'interval', minutes=30)