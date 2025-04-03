import os, sys, pytest

# Добавляем корневую директорию в PYTHONPATH
# (чтобы Python не заблудился в трёх соснах 🌲🌲🌲)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


@pytest.fixture
async def db_session():
    """Фикстура для тестовой сессии БД (наше спасение!)"""
    async with AsyncSessionFactory() as session:
        yield session