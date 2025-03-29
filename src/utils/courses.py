import json
import aiosqlite
from src.utils.db import DB_PATH

async def verify_course_code(code: str, user_id: int) -> tuple[bool, str, str]:
    with open('src/data/courses.json', 'r', encoding='utf-8') as f:
        courses = json.load(f)
    
    for course_id, course in courses.items():
        if not course['is_active']:
            continue
            
        for tier, tier_data in course['tiers'].items():
            if not tier_data['is_active']:
                continue
                
            if tier_data['code'].lower() == code.lower():
                # Check if user already has this course
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute('''
                        SELECT 1 FROM user_courses 
                        WHERE user_id = ? AND course_id = ?
                    ''', (user_id, course_id))
                    
                    if await cursor.fetchone():
                        return False, "", ""
                    
                    # Activate course for user
                    await db.execute('''
                        INSERT INTO user_courses (user_id, course_id, tier)
                        VALUES (?, ?, ?)
                    ''', (user_id, course_id, tier))
                    await db.commit()
                    
                return True, course_id, tier
                
    return False, "", ""