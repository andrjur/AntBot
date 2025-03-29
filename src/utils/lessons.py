import os
import re
from typing import List, Dict
import aiofiles
import markdown2

async def get_lesson_materials(course_id: str, lesson_number: int) -> List[Dict]:
    materials = []
    lesson_pattern = f"lesson{lesson_number}_"
    course_path = f"c:/Trae/AntBot/data/courses/{course_id}"
    
    if not os.path.exists(course_path):
        return materials
        
    for filename in os.listdir(course_path):
        if filename.startswith(lesson_pattern):
            file_path = os.path.join(course_path, filename)
            
            # Handle text files
            if filename.endswith('.txt'):
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                materials.append({
                    'type': 'text',
                    'content': content
                })
            
            # Handle markdown files
            elif filename.endswith('.md'):
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                html_content = markdown2.markdown(content)
                materials.append({
                    'type': 'text',
                    'content': html_content
                })
            
            # Handle video files
            elif filename.endswith(('.mp4', '.avi', '.mov')):
                materials.append({
                    'type': 'video',
                    'file_path': file_path
                })
            
            # Handle images
            elif filename.endswith(('.jpg', '.jpeg', '.png')):
                materials.append({
                    'type': 'photo',
                    'file_path': file_path
                })
    
    return materials