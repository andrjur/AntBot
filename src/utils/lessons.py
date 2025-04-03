import os
import aiofiles
import logging

logger = logging.getLogger(__name__)

async def get_lesson_materials(course_id: str, lesson: int):
    # Исправляем путь к урокам - у нас lesson{N}, а не lessons/lesson_{N}
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Корень проекта
    lesson_dir = os.path.join(base_dir, "data", "courses", course_id, f"lesson{lesson}")
    
    logger.info(f"Ищем материалы в директории: {lesson_dir}")
    
    materials = []
    try:
        # Проверяем, существует ли директория
        if not os.path.exists(lesson_dir):
            logger.error(f"Директория урока не найдена: {lesson_dir}")
            return []
            
        for filename in os.listdir(lesson_dir):
            file_path = os.path.join(lesson_dir, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
                
            # Determine type by extension
            ext = os.path.splitext(filename)[1].lower()
            
            if ext in ['.txt', '.md']:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                materials.append({
                    'type': 'text',
                    'content': content,
                    'file_path': file_path
                })
                logger.info(f"Загрузили текст из {file_path}")
                
            elif ext in ['.jpg', '.jpeg', '.png']:
                materials.append({
                    'type': 'photo',
                    'file_path': file_path
                })
                logger.info(f"Добавили фото: {file_path}")
                
            elif ext in ['.mp4', '.avi', '.mov']:
                materials.append({
                    'type': 'video',
                    'file_path': file_path
                })
                logger.info(f"Добавили видео: {file_path}")
                
        # Sort materials by filename to maintain order
        materials.sort(key=lambda x: x['file_path'])
        
        return materials
    except Exception as e:
        logger.error(f"Ошибка загрузки материалов: {e}")
        return []


async def add_lesson_to_course(course_id: str, lesson_data: dict):
    """Add new lesson to course (moved from services/course.py)"""
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