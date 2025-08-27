import logging
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os

# Загрузка переменных из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot_debug.log')]
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
API_KEY = os.environ.get('API_KEY')

if not TELEGRAM_TOKEN or not API_KEY:
    logger.critical("Отсутствует TELEGRAM_TOKEN или API_KEY в .env")
    raise ValueError("Необходимо задать TELEGRAM_TOKEN и API_KEY в .env")

# Список лиг с кодами
LEAGUES = {
    '🏴 Англия (Premier League)': 'PL',
    '🇪🇸 Испания (La Liga)': 'PD',
    '🇩🇪 Германия (Bundesliga)': 'BL1',
    '🇫🇷 Франция (Ligue 1)': 'FL1',
    '🇮🇹 Италия (Serie A)': 'SA',
    '🇳🇱 Нидерланды (Eredivisie)': 'DED',
    '🇵🇹 Португалия (Primeira Liga)': 'PPL',
    '🇺🇦 Украина (Premier League)': 'UPL',  # будет парсинг
    '🇧🇪 Бельгия (Pro League)': 'BPD',
    '🏴 Шотландия (Premiership)': 'SPL'
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_state = {}

def create_leagues_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    buttons = [KeyboardButton(league) for league in LEAGUES.keys()]
    keyboard.add(*buttons)
    return keyboard

def create_date_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    today = date.today().strftime('%Y-%m-%d')
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    keyboard.add(
        InlineKeyboardButton("Сегодня", callback_data=f"date_{today}"),
        InlineKeyboardButton("Завтра", callback_data=f"date_{tomorrow}")
    )
    return keyboard

def fetch_fixtures(league_code: str, match_date: str) -> str:
    """Получает расписание матчей для указанной лиги и даты."""
    if league_code == "UPL":
        return fetch_upl_fixtures(match_date)
    else:
        return fetch_api_fixtures(league_code, match_date)

def fetch_api_fixtures(league_code: str, match_date: str) -> str:
    """Получает расписание матчей через Football-Data.org API"""
    logger.info(f"API-запрос: лига={league_code}, дата={match_date}")
    url = f'https://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={match_date}&dateTo={match_date}'
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        matches = data.get('matches', [])

        if not matches:
            return f"⚽ На {match_date} нет матчей в этой лиге."

        result = f"📅 Расписание матчей на {match_date}:\n\n"
        for match in matches:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            time_utc = match['utcDate'][11:16]
            status = match['status']
            result += f"🏟️ {home} vs {away}\n🕒 Время (UTC): {time_utc}\n📊 Статус: {status}\n\n"
        return result
    except requests.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        return "❌ Ошибка при получении данных. Попробуйте позже."

def fetch_upl_fixtures(match_date: str) -> str:
    """Парсит расписание матчей УПЛ"""
    logger.info(f"Парсим УПЛ на {match_date}")
    url = "https://football.ua/ukraine.html"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Блок с матчами
        matches_block = soup.find("div", class_="main-content")
        if not matches_block:
            return "⚠ Не удалось найти расписание матчей УПЛ."

        result = f"📅 Расписание УПЛ на {match_date}:\n\n"
        matches = matches_block.find_all("div", class_="match-block")
        found = False

        for match in matches:
            date_tag = match.find("div", class_="match-date")
            if not date_tag:
                continue

            # Дата матча на сайте может быть в формате '27.08.2025'
            date_str = date_tag.text.strip()
            date_parts = date_str.split('.')
            if len(date_parts) == 3:
                site_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
            else:
                continue

            # Сравниваем даты
            if site_date != match_date:
                continue

            home_team = match.find("div", class_="team1").text.strip()
            away_team = match.find("div", class_="team2").text.strip()
            time_tag = match.find("div", class_="match-time")
            match_time = time_tag.text.strip() if time_tag else "Время уточняется"

            result += f"🏟️ {home_team} vs {away_team}\n🕒 Время: {match_time}\n\n"
            found = True

        if not found:
            return f"⚽ На {match_date} нет матчей УПЛ."
        return result

    except requests.RequestException as e:
        logger.error(f"Ошибка парсинга УПЛ: {e}")
        return "❌ Ошибка при подключении к football.ua."
    except Exception as e:
        logger.error(f"Неожиданная ошибка парсинга УПЛ: {e}")
        return "⚠ Произошла ошибка при обработке данных УПЛ."

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    user_state[message.chat.id] = {}
    welcome_text = (
        "⚽ Добро пожаловать в Football Schedule Bot!\n"
        "Выберите лигу, затем выберите дату.\n\n"
        "Команды:\n/start - Начать\n/help - Показать помощь"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_leagues_keyboard())

@bot.message_handler(func=lambda message: message.text in LEAGUES)
def handle_league_selection(message):
    user_state[message.chat.id] = {'league': message.text}
    bot.send_message(
        message.chat.id,
        f"Вы выбрали {message.text}. Теперь выберите дату:",
        reply_markup=create_date_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
def handle_date_selection(call):
    chat_id = call.message.chat.id
    if chat_id not in user_state or 'league' not in user_state[chat_id]:
        bot.answer_callback_query(call.id, "Сначала выберите лигу!")
        return

    league_name = user_state[chat_id]['league']
    league_code = LEAGUES[league_name]
    match_date = call.data.split('_')[1]

    fixtures_info = fetch_fixtures(league_code, match_date)
    bot.send_message(chat_id, fixtures_info)
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "Выберите другую лигу или дату:", reply_markup=create_leagues_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(message.chat.id, "Пожалуйста, выберите лигу из меню или используйте /start.")

if __name__ == '__main__':
    logger.info("Запуск бота...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
