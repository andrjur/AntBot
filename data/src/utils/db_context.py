import aiosqlite
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/bot.db"
db_connection = None

@asynccontextmanager
async def get_db():
    global db_connection
    if db_connection is None:
        db_connection = await aiosqlite.connect(DB_PATH)
    try:
        yield db_connection
    finally:
        if db_connection:
            await db_connection.close()
            db_connection = None