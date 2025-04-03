from datetime import datetime, timedelta
import asyncio
from typing import Dict, Tuple
import logging
from functools import wraps
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URL = "sqlite+aiosqlite:///c:/Trae/AntBot/data/bot.db"
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

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
        async with async_session() as session:
            try:
                stmt = text('''
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
                await session.execute(stmt)
                await session.commit()
                
                result = await session.execute(text('SELECT * FROM course_stats'))
                stats = await result.fetchall()
                for stat in stats:
                    self._cache[(stat[0], stat[1])] = {
                        'total_active': stat[2],
                        'total_completed': stat[3],
                        'avg_completion_time': stat[4],
                        'last_updated': stat[5]
                    }
            except Exception as e:
                logger.error(f"Error updating stats: {e}")
                await session.rollback()
                raise
    
    async def get_stats(self, course_id: str, lesson: int) -> Dict:
        return self._cache.get((course_id, lesson), {
            'total_active': 0,
            'total_completed': 0,
            'avg_completion_time': 0
        })


def cache_with_timeout(seconds):
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key in cache:
                timestamp, result = cache[key]
                if time.time() - timestamp < seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (time.time(), result)
            return result
            
        return wrapper
    return decorator


# В конец файла добавить
async def shutdown():
    await engine.dispose()

# И в StatsCache добавить метод закрытия
async def close(self):
    await shutdown()
    self._update_task.cancel()

