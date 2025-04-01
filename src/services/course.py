from src.utils.db import safe_db_operation
import logging

logger = logging.getLogger(__name__)

async def get_course_progress(user_id: int, course_id: str):
    """Получаем прогресс пользователя по курсу 📊"""
    logger.info(f"4001 | Запрашиваем прогресс для user_id={user_id}, course={course_id} 📈")
    async with aiosqlite.connect(DB_PATH) as db:
        # Add lesson metadata
        await db.execute(
            '''
            INSERT INTO lessons 
            (lesson_number, name, description, course_id)
            VALUES (?, ?, ?, ?)
            ''',
            (lesson_data['lesson'], 
             lesson_data['lesson_name'],
             lesson_data['description'],
             course_id)
        )
        lesson_id = db.last_insert_rowid()
        
        # Add media files
        for content in lesson_data['content']:
            await db.execute(
                '''
                INSERT OR IGNORE INTO media_files 
                (file_id, type, url, caption, course_id)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (content['file_id'],
                 content['type'],
                 content['url'],
                 content.get('caption', ''),
                 course_id)
            )
            # Link file to lesson
            await db.execute(
                '''
                INSERT INTO lesson_media 
                (lesson_id, file_id)
                VALUES (?, ?)
                ''',
                (lesson_id, content['file_id'])
            )
        
        await db.commit()