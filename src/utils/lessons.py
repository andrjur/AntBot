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