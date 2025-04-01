import json
import logging
import os

logger = logging.getLogger(__name__)

def get_courses_data() -> dict:
    """Load courses data from cache"""
    try:
        cache_file = os.path.join('data', 'courses', 'courses.json')
        if not os.path.exists(cache_file):
            logger.error(f"Courses cache file not found: {cache_file}")
            return {}
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        logger.error(f"Error loading courses data: {e}")
        return {}