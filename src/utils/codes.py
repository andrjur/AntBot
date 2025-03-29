async def verify_activation_code(code: str, user_id: int) -> tuple[bool, str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT course_id, tier, is_used 
            FROM activation_codes 
            WHERE code = ?
        ''', (code,))
        result = await cursor.fetchone()
        
        if not result:
            return False, "", ""
            
        course_id, tier, is_used = result
        
        if is_used:
            return False, "", ""
            
        # Check if course and tier are active
        cursor = await db.execute('''
            SELECT tiers FROM courses WHERE course_id = ?
        ''', (course_id,))
        course = await cursor.fetchone()
        tiers = json.loads(course[0])
        
        if not tiers.get(tier, {}).get('is_active', False):
            return False, "", ""
            
        # Mark code as used
        await db.execute('''
            UPDATE activation_codes 
            SET is_used = TRUE, 
                used_at = datetime('now'),
                used_by = ?
            WHERE code = ?
        ''', (user_id, code))
        await db.commit()
        
        return True, course_id, tier