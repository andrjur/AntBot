import pytest
from unittest.mock import patch, mock_open
from src.utils.lessons import get_lesson_materials

from unittest.mock import AsyncMock, patch, mock_open, MagicMock
import aiofiles
import os
from src.utils.lessons import get_lesson_materials

class AsyncContextManagerMock:
    async def __aenter__(self):
        return self  # Теперь возвращаем сам объект
    async def __aexit__(self, *args):
        pass
    async def read(self):  # Добавляем асинхронный метод чтения
        return "Текст урока"

@pytest.mark.asyncio
async def test_get_lesson_materials():
    with patch('os.listdir') as mock_listdir, \
         patch('os.path.isdir', return_value=False), \
         patch('os.path.splitext') as mock_splitext, \
         patch('aiofiles.open', return_value=AsyncContextManagerMock()):
        
        # Настраиваем возвращаемые значения
        mock_listdir.return_value = [
            '01_theory.txt',
            '02_task.jpg',
            '03_example.mp4'
        ]
        
        # Настраиваем splitext для возврата правильных расширений
        def side_effect_splitext(filename):
            if '01_theory.txt' in filename:
                return ['01_theory', '.txt']
            elif '02_task.jpg' in filename:
                return ['02_task', '.jpg']
            elif '03_example.mp4' in filename:
                return ['03_example', '.mp4']
            return ['', '']
        
        mock_splitext.side_effect = side_effect_splitext
        
        # Вызываем тестируемую функцию
        materials = await get_lesson_materials('test_course', 1)
        
        # Проверяем результаты
        assert len(materials) == 3
        assert materials[0]['type'] == 'text'
        assert materials[0]['content'] == 'Текст урока'
        assert materials[1]['type'] == 'photo'
        assert materials[2]['type'] == 'video'
        
        # Проверяем сортировку
        assert '01_theory' in materials[0]['file_path']
        assert '02_task' in materials[1]['file_path']
        assert '03_example' in materials[2]['file_path']

@pytest.mark.asyncio
async def test_get_lesson_materials_empty():
    """Тестируем пустую директорию урока 📂"""
    with patch('os.listdir', return_value=[]):
        materials = await get_lesson_materials('test_course', 1)
        assert materials == []

@pytest.mark.asyncio
async def test_get_lesson_materials_error():
    """Тестируем обработку ошибок 🚫"""
    with patch('os.listdir', side_effect=FileNotFoundError):
        materials = await get_lesson_materials('test_course', 1)
        assert materials == []