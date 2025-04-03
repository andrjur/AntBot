import pytest
from src.utils.cache import StatsCache

@pytest.mark.asyncio
async def test_stats_cache_update(db_session):
    cache = StatsCache()
    await cache._update_stats()
    
    stats = await cache.get_stats("test_course", 1)
    assert isinstance(stats, dict)
    assert 'total_active' in stats