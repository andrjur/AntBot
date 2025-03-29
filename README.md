# AntBot - Telegram Course Bot

A Telegram bot for managing online courses with different tiers and homework verification.

## Features

- User registration
- Course activation via code words
- Multiple course tiers:
  - Self-check (without homework verification)
  - Admin-check (with homework verification)
  - Premium (with consultations)
- Homework submission and review system
- Admin panel for course management

## Setup

1. Create virtual environment:
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

## Admin Commands
- /generate_codes - Generate activation codes
- Other admin commands...
## Course Configuration
Courses are configured in src/data/courses.json :

```json
{
```