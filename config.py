import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Ошибка: не найден TELEGRAM_TOKEN в файле .env")

if not FOOTBALL_API_KEY:
    raise ValueError("Ошибка: не найден FOOTBALL_API_KEY в файле .env")

