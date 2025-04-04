# AntBot - Бот для проведения онлайн-курсов

Telegram-бот для управления онлайн-курсами с разными тарифами и проверкой домашних заданий.

## Возможности

- Регистрация пользователей
- Активация курсов по кодовым словам
- Тарифы курсов:
  - Самопроверка (без проверки ДЗ)
  - Проверка админом
  - Премиум (с консультациями)
- Автоматическая отправка уроков
- Система проверки домашних заданий
- Кэширование медиафайлов
- Тестовый режим для отладки

## Установка

1. Создание виртуального окружения:
```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
 ```

3. Configure environment variables in .env :
```plaintext
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
ADMIN_GROUP_ID=-100...
 ```

4. Initialize database:
```bash
python -m src.utils.db
 ```

5. Run the bot:
```bash
python -m src.main
 ```

## Project Structure
```plaintext
AntBot/
├── src/
│   ├── handlers/      # Message handlers
│   ├── keyboards/     # Telegram keyboards
│   ├── services/      # Business logic
│   ├── utils/         # Utilities
│   └── main.py        # Entry point
├── .env              # Environment variables
└── requirements.txt  # Dependencies
 ```


## Структура файлов курсов

Файлы курсов должны располагаться в следующей структуре:

1. Структура каталогов для нового курса:
```plaintext
c:\Trae\AntBot\data\courses\femininity\
├── lessons.json
├── lesson1\
│   ├── intro.txt
│   └── practice1.txt
├── lesson2\
│   ├── intro.txt
│   └── practice2.txt
└── ...
 ```


### Важные замечания

1. Все файлы должны быть в формате UTF-8
2. Поддерживаются форматы: .txt, .md
4. Папки уроков нумеруются последовательно: lesson1, lesson2, ...

### Система задержек
Задержки указываются в именах файлов:

- файл_Xmin.txt - отправка через X минут
- файл_Yhour.txt - отправка через Y часов
Примеры:

- task_15min.txt → задержка 15 минут
- theory_1hour.txt → задержка 1 час
- intro.txt → без задержки (мгновенная отправка)
### Тестовый режим
При включении:

- Все задержки файлов сокращаются до 30 секунд
- Интервал между уроками сокращается до 5 минут
- Включается через TEST_MODE=1 в .env
### Кэширование медиафайлов
- Медиафайлы (видео, фото, аудио) кэшируются в lessons.json
- Предотвращает повторную загрузку одних и тех же файлов
- При замене файла с тем же именем:
  1. Сначала проверяется существующий file_id
  2. При ошибке загружается новая версия
  3. Кэш автоматически обновляется
- Проверка кэша при запуске бота
## Команды администратора
- /start - Запуск бота
- /generate_codes - Генерация кодов активации
- /stats - Просмотр статистики
## Разработка
- Python 3.11+
- aiogram 3.x
- SQLite база данных

### Тестовый режим
При включении:

- Все задержки файлов сокращаются до 30 секунд
- Интервал между уроками сокращается до 5 минут
- Включается через TEST_MODE=1 в .env
### Кэширование медиафайлов
- Медиафайлы (видео, фото, аудио) кэшируются в lessons.json
- Предотвращает повторную загрузку одних и тех же файлов
- При замене файла с тем же именем:
  1. Сначала проверяется существующий file_id
  2. При ошибке загружается новая версия
  3. Кэш автоматически обновляется
- Проверка кэша при запуске бота




pytest -v tests/ --html=report.html

python -m src.main         
