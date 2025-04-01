import json
import aiosqlite
from src.utils.db import DB_PATH

async def init_codes_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS used_codes (
                code TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.commit()

async def is_code_used(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT 1 FROM used_codes WHERE code = ?', (code,))
        return bool(await cursor.fetchone())

async def mark_code_used(code: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO used_codes (code, user_id)
            VALUES (?, ?)
        ''', (code, user_id))
        await db.commit()

async def verify_activation_code(code: str, user_id: int) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT course_id, is_used 
            FROM activation_codes 
            WHERE code = ?
        ''', (code,))
        result = await cursor.fetchone()
        
        if not result:
            return False, ""
            
        course_id, is_used = result
        
        if is_used:
            return False, ""
            
        # Mark code as used
        await db.execute('''
            UPDATE activation_codes 
            SET is_used = TRUE, 
                used_at = datetime('now'),
                used_by = ?
            WHERE code = ?
        ''', (user_id, code))
        await db.commit()
        
        return True, course_id