import aiosqlite
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Tuple
import logging
from .db import DB_PATH

logger = logging.getLogger(__name__)

class StatsCache:
    _instance = None
    _cache: Dict[Tuple[str, int], Dict] = {}
    _cache_ttl = 300  # 5 minutes
    
    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = StatsCache()
            await cls._instance.init()
        return cls._instance
    
    async def init(self):
        self._update_task = asyncio.create_task(self._periodic_update())
    
    async def _periodic_update(self):
        while True:
            try:
                await self._update_stats()
                await asyncio.sleep(self._cache_ttl)
            except Exception as e:
                logger.error(f"Cache update error: {e}")
                await asyncio.sleep(60)
    
    async def _update_stats(self):
        async with aiosqlite.connect(DB_PATH) as db:
            # Update active users and homework stats
            await db.execute('''
                INSERT OR REPLACE INTO course_stats 
                SELECT 
                    uc.course_id,
                    uc.current_lesson,
                    COUNT(DISTINCT uc.user_id) as total_active,
                    COUNT(DISTINCT CASE WHEN h.status = 'approved' THEN h.user_id END) as total_completed,
                    AVG(CASE 
                        WHEN h.status = 'approved' 
                        THEN ROUND((julianday(h.approved_at) - julianday(h.sent_at)) * 24 * 60 * 60)
                        END) as avg_completion_time
                FROM user_courses uc
                LEFT JOIN homework h ON h.user_id = uc.user_id 
                    AND h.course_id = uc.course_id 
                    AND h.lesson = uc.current_lesson
                GROUP BY uc.course_id, uc.current_lesson
            ''')
            await db.commit()
            
            # Update cache
            cursor = await db.execute('SELECT * FROM course_stats')
            stats = await cursor.fetchall()
            for stat in stats:
                self._cache[(stat[0], stat[1])] = {
                    'total_active': stat[2],
                    'total_completed': stat[3],
                    'avg_completion_time': stat[4],
                    'last_updated': stat[5]
                }
    
    async def get_stats(self, course_id: str, lesson: int) -> Dict:
        return self._cache.get((course_id, lesson), {
            'total_active': 0,
            'total_completed': 0,
            'avg_completion_time': 0
        })