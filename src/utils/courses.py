import json
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def load_courses():
    """Load courses from JSON file"""
    with open('data/courses.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def verify_code(code: str) -> Tuple[bool, str]:
    """Verify course code and return course_id if valid"""
    courses = load_courses()
    
    for course_id, course in courses.items():
        if not course.get('is_active', False):
            continue
            
        if course['code'].lower() == code.lower():
            return True, course_id
            
    return False, ""