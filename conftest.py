import os
import sys

# Добавляем корневую директорию в PYTHONPATH
# (чтобы Python не заблудился в трёх соснах 🌲🌲🌲)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))