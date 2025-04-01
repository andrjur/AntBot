import os
import aiofiles
import logging

logger = logging.getLogger(__name__)

async def get_lesson_materials(course_id: str, lesson: int):
    # Исправляем путь как правильную тропинку для муравья 🐜
    lesson_dir = f"data/courses/{course_id}/lessons/lesson_{lesson}"
    
    materials = []
    try:
        for filename in os.listdir(lesson_dir):  # Теперь путь верный!
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
                logger.info(f"Loaded text from {file_path}")
                
            elif ext in ['.jpg', '.jpeg', '.png']:
                materials.append({
                    'type': 'photo',
                    'file_path': file_path
                })
                logger.info(f"Added photo: {file_path}")
                
            elif ext in ['.mp4', '.avi', '.mov']:
                materials.append({
                    'type': 'video',
                    'file_path': file_path
                })
                logger.info(f"Added video: {file_path}")
                
        # Sort materials by filename to maintain order
        materials.sort(key=lambda x: x['file_path'])
        
        return materials
    except Exception as e:
        logger.error(f"Error loading materials: {e}")
        return []