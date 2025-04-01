import re
import json
import os
import logging
from datetime import datetime, timedelta
from src.config import extract_delay_from_filename
from src.utils.course_cache import get_courses_data  # Changed import

logger = logging.getLogger(__name__)



def verify_code(code: str) -> tuple[bool, str, str]:
    """
    Verify course activation code
    Returns: (is_valid, course_id, version_id)
    """
    try:
        courses = get_courses_data()  # Using cached version
        for course_id, course in courses.items():
            for version in course['versions']:
                if version['code'] == code:
                    return True, course_id, version['id']
                    
        return False, None, None
        
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        return False, None, None

def get_lesson_files(course_id: str, lesson_number: int) -> list[dict]:
    """Get lesson files with their delays"""
    course_path = f"data/courses/{course_id}/lesson{lesson_number}"
    logger.info(f"📂 555 Scanning directory: {course_path}")
    
    if not os.path.exists(course_path):
        logger.warning(f"📁 Lesson directory not found: {course_path}")  # Changed to warning
        return []
        
    files = []
    
    for filename in os.listdir(course_path):
        file_path = os.path.join(course_path, filename)
        if not os.path.isfile(file_path):
            continue
            
        # Use extract_delay_from_filename from config
        delay = extract_delay_from_filename(filename)
        if delay > 0:
            logger.info(f"⏰ 5557 File {filename}: {delay} seconds delay")
        else:
            logger.info(f"📄 5558 File {filename}: no delay")
            
        files.append({
            'path': file_path,
            'delay': delay
        })
    
    sorted_files = sorted(files, key=lambda x: x['delay'])
    logger.info(f"📚 5559 Found {len(files)} files, sorted by delay")
    return sorted_files
    